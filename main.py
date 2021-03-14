import json, logging, os
from datetime import datetime, timezone, timedelta
from apscheduler.scheduler import Scheduler
from flask import Flask, Response
from slack import WebClient
from slackeventsapi import SlackEventAdapter
from threading import Thread
from twitter_requests import oauth

with open('config.json') as f:
    config = json.load(f)

# Initialize a Flask app to host the bot
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Initialize time variable to remember the last time tweets were checked
last_checked = datetime.now(timezone.utc)
last_checked = last_checked.isoformat()

# Define the base urls
search_url = "https://api.twitter.com/2/tweets/search/recent"
post_url = "https://api.twitter.com/1.1/statuses/update.json"

# Create an events adapter and register it to an endpoint in the slack app for event ingestion
slack_events_adapter = SlackEventAdapter(os.environ.get("SLACK_SIGNING_SECRET"), "/slack/events", app)

# Initialize a Slack web client
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))


# Detects a message and forwards the payload for processing
@slack_events_adapter.on("message")
def message(payload):
    # Get the event data from the payload
    event = payload.get("event", {})

    # Ignore bot messages
    if "bot_id" in event.keys():
        return

    # Get the channel ID for the reply
    channel_id = event.get("channel")

    # Get the text from the message
    text = event.get("text")

    if text is None:
        return

    # Send the task to a separate thread
    thr = Thread(target=handle_commands, args=[text, channel_id])
    thr.start()

    return Response(status=200)


# Handles user commands
def handle_commands(text, channel_id):
    # Check for any of the predetermined commands
    if text == "now":
        time_message = get_time_message()
        slack_client.chat_postMessage(channel=channel_id, text=time_message)
        return

    # Split the text to identify the new-content command and present the matching content
    command = text.split()

    if command[0] == "new-content":
        # Set default language to python
        language = "python"

        if len(command) == 2:
            language = command[1]
        elif len(command) > 2:
            slack_client.chat_postMessage(channel=channel_id, text="Usage: new-content language\nDefaults to Python.")
            return

        get_tweets(language.lower(), channel_id)

    if command[0] == "tweet":
        if len(command) == 1:
            slack_client.chat_postMessage(channel=channel_id, text="Usage: tweet text")
            return

        post_tweet(text)


# Fetches tweets from Twitter
def get_tweets(language, channel_id):
    # Get sources according to language
    with open('sources.json') as file:
        sources_file = json.load(file)

    # A flag used to indicate if any tweets were found
    found_tweets = False

    if language in sources_file.keys():
        sources = sources_file[language]

        if sources:
            time = datetime.now(timezone.utc) - timedelta(hours=config["hours_to_fetch"])
            time = time.isoformat()

            for source in sources:
                params = {"query": f"from:{source}", "start_time": time, "max_results": 20}
                response = oauth.get(search_url, params=params)

                if response.status_code != 200:
                    app.logger.error(f"There was an issue while getting tweets. Error code: {response.status_code}")
                    return

                body = json.loads(response.text)

                if "data" in body.keys():
                    message_tweets(body, source, channel_id)
                    found_tweets = True

                    # The next_token key appears if there are too many tweets in the payload, and is used
                    # to get the next batch
                    while "next_token" in body.keys():
                        new_url = f"{search_url}?next_token={body['next_token']}"
                        response = oauth.get(new_url, params=params)

                        if response.status_code != 200:
                            app.logger.error(
                                f"There was an issue while getting tweets. Error code: {response.status_code}")
                            return

                        body = json.loads(response.text)

                        if "data" in body.keys():
                            message_tweets(body, source, channel_id)

            # Notify the user that there have been no new tweets from the defined amount of hours in the past
            if not found_tweets:
                slack_client.chat_postMessage(channel=channel_id,
                                              text=f"No new tweets were found from the last "
                                                   f"{config['hours_to_fetch']} hour(s).")
        else:
            slack_client.chat_postMessage(channel=channel_id,
                                          text="No sources found for this language. Try adding some in the json!\n"
                                               "Usage: new-content language")
    else:
        slack_client.chat_postMessage(channel=channel_id,
                                      text="Language was not found in the sources file. Try adding it to the json!\n"
                                           "Usage: new-content language")


# Returns a string message with the current time
def get_time_message():
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")

    return "The time is " + str(current_time)


# Check for new tweets by requesting all tweets from the last time the check was performed, and update for the next time
def check_for_new_tweets():
    app.logger.info("Checking for new tweets...")
    user = config['user']
    channel = config['channel']
    global last_checked

    params = {"query": f"from:{user}", "tweet.fields": ["created_at"], "start_time": last_checked, "max_results": 20}
    response = oauth.get(search_url, params=params)

    if response.status_code != 200:
        app.logger.error(f"There was an issue while checking for new tweets. Error code: {response.status_code}")
        return

    # Update the last checked time
    time = datetime.now(timezone.utc)
    time = time.isoformat()
    last_checked = time

    body = json.loads(response.text)

    if "data" in body.keys():
        message_tweets(body, user, channel)

        # The next_token key appears if there are too many tweets in the payload, and is used to get the next batch
        while "next_token" in body.keys():
            new_url = f"{search_url}?next_token={body['next_token']}"
            response = oauth.get(new_url, params=params)
            body = json.loads(response.text)

            if "data" in body.keys():
                message_tweets(body, user, channel)


# Send the tweets in Slack via the bot
def message_tweets(body, source, channel_id):
    data = body["data"]

    # Reverse the list of tweets so that they are sent in chronological order in Slack
    for tweet in reversed(data):
        text = f'@{source}: {tweet["text"]}'
        slack_client.chat_postMessage(channel=channel_id, text=text)

    app.logger.info("Tweet(s) messaged successfully!")


# Posts a tweet on Twitter through the Slack bot
def post_tweet(text):
    # Remove the tweet command
    text = text.split("tweet ")
    text = text[1]

    params = {"status": text}
    response = oauth.post(post_url, params=params)

    if response.status_code == 200:
        app.logger.info("Tweet posted successfully.")
    else:
        app.logger.error(f"There was an issue with posting the tweet. Error code: {response.status_code}")


def main():
    # Schedule hourly time message and checking for new tweets
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        schedule = Scheduler()
        schedule.add_interval_job(
            lambda: slack_client.chat_postMessage(channel=config["channel"], text=get_time_message()), hours=1)
        schedule.add_interval_job(
            check_for_new_tweets, seconds=30)
        schedule.start()

    app.logger.info("Bot tasks have been scheduled. Starting Flask server...")
    app.run(port=config["port"])


if __name__ == "__main__":
    main()

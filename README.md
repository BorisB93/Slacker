# Slacker
Welcome to Slacker, a Slack bot that communicates with Twitter for the latest programming news!

## Introduction
Slacker was built using Flask and slackclient. It communicates with Twitter via requests to the API, and uses
apscheduler to manage scheduled tasks.


After setting it up, Slacker will send a message with the current time every hour from the moment it woke up.
It will also automatically post tweets from your Twitter user, and will check for new tweets every few seconds.

In addition, Slacker comes with the following commands:
- now - Responds with the current time.
- new-content [language] - Responds with the latest tweets (default is 1 hour ago, value can be changed in config.json) from the list of users defined in sources.json,
according to the language argument if provided (python, java, etc). Defaults to Python if language is not provided. 
- tweet [text] - Tweets the given text from the Twitter user.


## Setup
First, you must set up your Slack workspace and bot permissions, and create a Twitter user and gain access to the Twitter API.

Instructions for Slack can be found here: https://api.slack.com/authentication/basics

Instructions for Twitter can be found here: https://developer.twitter.com/en/docs/twitter-api/getting-started/guide

Make sure your Slack and Twitter apps have all required permissions to communicate - for example, read AND write permissions for Twitter.


## Configurations

Clone this repository and install requirements:

#### `pip install -r requirements.txt`

After that, you must set the following environment variables:
- SLACK_SIGNING_SECRET
- SLACK_BOT_TOKEN
- TWITTER_API_KEY
- TWITTER_SECRET_KEY

Make sure to edit the config.json file:
- channel - Defaults to "content".
- user - Your Twitter handle.
- hours_to_fetch - The amount of hours in the past that tweets will be fetched. Default is one hour.
- port - The port used by Flask. Defaults to 3000.


## Run it!
Run the main.py file and enjoy!
Add more sources to sources.json to keep yourself up to date with the latest programming news!

* Note that you will be asked to authenticate your first Twitter request through the browser - just follow the link once Slacker
starts running and paste the PIN number in the input. 

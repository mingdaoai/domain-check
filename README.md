# Domain Name Chatbot

This directory contains a command line based chat application to help people find unique domain names for their web application.

## Usage

* it asks people what ideas they have for domain names.
* it generates a list of domain names based on the idea, and prints them to the console.
* it tests each domain name to see if it is available.
* If the domain name is available, it will be displayed in a list.  If the domain name is not available, it will be displayed in a list with a message that it is not available.

The user can further chat with the app to generate more ideas.

# Installation

On a Mac or Linux machine, run the following commands:

```
git clone https://github.com/mingdaoai/domain-check.git
cd domain-check
uv sync
./main.py
```

Alternatively, you can use pip: `pip install -r requirements.txt` and run `python main.py`.

The app uses DeepSeek's API to support chat and generate domain names.  The key of the DeepSeek API is saved in a file ~/.mingdaoai/deepseek.key

# License

MIT

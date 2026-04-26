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

## Domain Availability Checking

The app now uses a multi-step domain availability checking system:

1. **DNS Check**: First checks if the domain has any DNS records (A, AAAA, MX, NS, etc.). If DNS records exist, the domain is considered taken.
2. **AWS Route 53 API**: If no DNS records are found, checks domain availability using AWS Route 53 Domains API (requires AWS credentials).
3. **WHOIS Fallback**: If AWS check fails or credentials are not configured, falls back to traditional WHOIS lookup.

### AWS Configuration (Optional)

To use AWS Route 53 Domains API for more accurate availability checking:

1. **Install AWS CLI**: `pip install awscli` or configure boto3 directly
2. **Configure credentials**: Run `aws configure` or set environment variables:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`
   - `AWS_DEFAULT_REGION` (set to `us-east-1` for Route 53 Domains)
3. **IAM Permissions**: Ensure your AWS user has permission for `route53domains:CheckDomainAvailability`

If AWS credentials are not configured, the app will automatically fall back to WHOIS checking.

# License

MIT

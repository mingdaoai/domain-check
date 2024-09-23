import whois

def check_domain_availability(domain):
    try:
        domain_info = whois.whois(domain)
        return not domain_info.domain_name
    except whois.parser.PywhoisError:
        return True
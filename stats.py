#!env python

import datetime
import json
import sys
import collections

def run(args):
    with open(args[1]) as f:
        data = json.load(f)
    print_statuses(data)
    print_asset_classes(data)
    print_originator(data)
    print_order_depth(data)
    return 0


CLOSED_STATUSES = ('Repaid', 'Sold', 'CreditLoss')


def print_originator(data):
    dist = collections.Counter([e['Originator']+" (SBL Finans)" if e['Originator']=='Loanstep' else e['Originator'] for e in data if e['Status'] not in CLOSED_STATUSES])
    print_header("Originators")
    for status, count in dist.items():
        s = "{0:>30}: {1:.2f}% ({2})".format(status, 100.0*count/len(data), count)
        print(s)
    print()


def print_asset_classes(data):
    dist = collections.Counter([e['AssetClass'] for e in data if e['Status'] not in CLOSED_STATUSES])
    print_header("Asset classes")
    for status, count in dist.items():
        s = "{0:>20}: {1:.2f}% ({2})".format(status, 100.0*count/len(data), count)
        print(s)
    print()


def print_statuses(data):
    dist = collections.Counter([e['Status'] for e in data])
    print_header("Statuses")
    for status, count in dist.items():
        s = "{0:>20}: {1:.2f}% ({2})".format(status, 100.0*count/len(data), count)
        print(s)
    print()


def print_header(s):
    print(s)
    print("-"*len(s))


def print_order_depth(data):
    today = datetime.date.today()
    for e in data:
        e['daysUntilExpectedEndDate'] = datetime.date.fromisoformat(e['ExpectedEndDate'])-today
        # Assumption here is that interest is the same after the loan is due. Maybe that's not correct?
        e['duration'] = max(today, datetime.date.fromisoformat(e['ExpectedEndDate'])) - datetime.date.fromisoformat(e['CreditIssueDate'])

        e['dailyInterest'] = e['ExpectedAnnualInterest']**(1./365)
        e['claimWithInterest'] = e['Claim']*(1.+e['dailyInterest']**e['duration'].days)
    data.sort(key=lambda x: x['daysUntilExpectedEndDate'])
    data = [[e['daysUntilExpectedEndDate'], e['claimWithInterest'], e] for e in data if e['Status']!='Repaid']

    print_header("Order depth (cumulative, interest included)")
    percentiles = (0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99)
    for p in percentiles:
        index = round(p*(len(data)-1))
        s = "{0:>10}% {1:>25} {2:>10.2f} SEK".format(100*p, str(data[index][0]), sum([e[1] for e in data[:index+1]]))
        print(s)
    print()





if __name__=='__main__':
    sys.exit(run(sys.argv))

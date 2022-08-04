#!env python

import argparse
import datetime
import json
import logging
import math
import numpy
import pprint
import random
import simpy
import sys


DEBUG=True


# TODO: Make this command line configurable.

def main(argv):
    parser = argparse.ArgumentParser(description='Monte Carlo simulation of a Savelend portfolio.')
    parser.add_argument('by_portfolio_api', metavar='CREDITS_JSON', type=argparse.FileType(), help='the JSON response containing the list of credits. See README for details how to extract it.')
    parser.add_argument('--iterations', default=1000, type=int, help='number of Monte Carlo simulations to run.')
    parser.add_argument('--random-seed', type=int, help='seed for the random number generator. Useful to be able to recreate simulations.')
    parser.add_argument('--verbose', '-v', action='count', default=0)
    parser.add_argument('--initial-amount', default=10000., type=float, help='initial amount put into your portfolio.')
    parser.add_argument('--time-horison', default=365, type=int, metavar='DAYS', help='number of days to simulate.')

    args = parser.parse_args(argv[1:])
    run(args)


def run(args):
    configure_logging(args)
    if args.random_seed:
        random.seed(args.random_seed)

    data = json.load(args.by_portfolio_api)
    decorate(data)

    outcomes = [simulate(args, data) / args.initial_amount for i in range(args.iterations)]
    logging.debug('Simulation outcomes before normalisation: %s', outcomes)
    outcomes = [math.pow(d, 365./args.time_horison) for d in outcomes]   # Normalise growth to a year.
    logging.debug('Simulation outcomes after normalisation: %s', outcomes)

    print('Initial amount:       ', '{:.2f}'.format(args.initial_amount), 'SEK')
    print('Number of simulations:', len(outcomes))
    print()
    print('Summary of marginal gains (positive is profit, negative is loss):')

    template = '{0:>20}: {1:>5.2%} ({2:.2f} SEK)'
    mean = numpy.mean(outcomes)
    print(template.format('Average', mean-1, args.initial_amount * mean))

    for perc in (0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100):
        p = numpy.percentile(outcomes, perc)
        print(template.format('{0}th percentile:'.format(perc), p-1, args.initial_amount * p))

    print()
    print('(all percentages are yearly)')

    return 0


FORMAT = '%(levelname)s %(asctime)s %(message)s'


def configure_logging(args):
    level = logging.DEBUG if args.verbose else logging.WARN
    logging.basicConfig(format=FORMAT, level=level)


def simulate(args, data):
    env = simpy.Environment()
    wallet = simpy.resources.container.Container(env, init=args.initial_amount)
    invested = simpy.resources.container.Container(env, init=0.)
    env.process(autoinvest(env, data, wallet, invested, args.initial_amount))
    env.run(until=args.time_horison)
    return wallet.level + invested.level


def decorate(data):
    for e in data:
        dateformat = '%Y-%m-%dT%H:%M:%S.%fZ'
        investtime = datetime.datetime.strptime(e['FirstInvestmentTime'], dateformat).date()
        if e['Status']=='Repaid':
            endtime = datetime.datetime.strptime(e['ActualEndTime'], dateformat).date()
        else:
            endtime = datetime.date.fromisoformat(e['ExpectedEndDate'])
        e['investmentDuration'] = endtime - investtime

        e['dailyInterest'] = (1.+e['ExpectedAnnualInterest'])**(1./365)


ratios = {
        'Loanstep': {
            'ConsumerCredit': 0.02
            },
        'Treyd': {
            'Factoring': 0.01
            },
        'Billecta Factoring': {
            'Factoring': 0.01, # TODO: Double check this!
            },
        'Billecta Inkasso': {
            'DcPortfolio': 0.02, # TODO: Double check this!
            },
        'Billecta Företagskrediter': {
            'SMECredit': 0.015
            },
        'Billecta PL - SME': {
            'SMECredit': 0.03,
            },
        'SKF Hyresfastighet': {
            'SMECredit': 0.015
            },
        'Billecta FI - Factoring': {
            'Factoring': 0.01,
            }
        }



def autoinvest(env, credits, wallet, invested, init_amount):
    nextloanid = 0
    while True:
        total = 0
        while wallet.level > 0:
            # Assumption is we always fill up wallet within a day.

            credit = random.choice(credits)
            asset_class = ratios[credit['Originator']]
            if credit['AssetClass'] not in asset_class:
                raise Exception('Missing {0}:{1}.'.format(credit['Originator'], credit['AssetClass']))
            ratio = asset_class[credit['AssetClass']]
            
            total_portfolio_value = wallet.level + invested.level
            # Assumption here is that we aren't being offered claims smaller than the formula below.
            claim = min(ratio * total_portfolio_value, wallet.level)

            wallet.get(claim)
            invested.put(claim)
            env.process(consumer(env, nextloanid, credit, wallet, invested, claim))
            nextloanid += 1
        yield env.timeout(1)
        

def consumer(env, loanid, credit, wallet, invested, claim):
    # Assumption autoinvest invests on the following day.
    yield env.timeout(1)
    days = credit['investmentDuration'].days
    claimWithInterest = claim*(credit['dailyInterest']**days) if days > 14 else claim

    loggingData = {'now': env.now, 'loanid': loanid, 'claim': claim, 'wallet.level': wallet.level, 'invested.level': invested.level, 'claimWithInterest': claimWithInterest, 'days': days}
    logging.info('Initiating a loan. Details: %s', loggingData)

    yield env.timeout(days)
    if claimWithInterest > 0:
        wallet.put(claimWithInterest)
        invested.get(claim)

    logging.info('Loan repaid. Details: %s', loggingData, extra={'now': env.now})


if __name__=='__main__':
    sys.exit(main(sys.argv))

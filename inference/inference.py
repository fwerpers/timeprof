import datetime
import numpy as np
from schedule import Activity, RandomSchedule
import time
from scipy.special import gammainccinv, gammaincinv
import json

def get_random_interval(mean_interval):
    """Generates a random interval (datetime.timedelta) using the exponential distribution"""
    minutes = np.ceil(np.random.exponential(scale=mean_interval))
    duration = datetime.timedelta(0, minutes*60, 0)
    return(duration)

def generate_sample_times(start, end, mean_interval):
    """Returns a list of sample times (datetime.datetime)"""
    times = [start]
    while True:
        duration = get_random_interval(mean_interval)
        next_time = times[-1] + duration
        if next_time > end:
            break
        times.append(next_time)

    return(times)

def normal_approximation_interval(tag_samples, tag):
    """Implementation from:
    https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
    """
    N = float(len(tag_samples))
    n = float(np.sum(tag_samples == tag))
    z = 1.96 # 95% confidence interval
    p = n/N
    interval_term = z*np.sqrt(p*(1-p)/N)
    low = p - interval_term
    high = p + interval_term
    res = np.array([low, p, high])
    return(res)

def wilson_score_interval(tag_samples, tag):
    """Implementation from:
    https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval
    """
    N = float(len(tag_samples))
    n = float(np.sum(tag_samples == tag))

    z = 1.96 # 95% confidence interval
    p = n/N
    factor = 1/(1+z**2/N)
    base_term = p + z**2/(2*N)
    interval_term = z*np.sqrt(p*(1-p)/N+z**2/(4*N**2))
    low = factor*(base_term - interval_term)
    high = factor*(base_term + interval_term)
    res = np.array([low, p, high])
    return(res)

def gamma_tom_jack(tag_samples, tag):
    """Implementation from discussion on:
    http://messymatters.com/tagtime/
    (Tom Jack)
    """
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)

    g = 0.75
    c = 0.95
    low = g*gammainccinv(n, (1+c)/2)
    high = g*gammainccinv(n+1, (1-c)/2)
    res = np.array([low, high])
    return(res/N)

def gamma_daniel_reeves(tag_samples, tag):
    """Implementation from discussion on:
    http://messymatters.com/tagtime/
    (Daniel Reeves)
    """
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)

    g = 0.75
    c = 0.95
    low = g*gammainccinv(n, (1+c)/2)
    high = g*gammainccinv(n, (1-c)/2)
    res = np.array([low, high])
    return(res/N)

def gamma_brute(tag_samples, tag):
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)
    c = 0.95
    low = gammainccinv(n, (1+c)/2)
    high = gammainccinv(n, (1-c)/2)
    res = np.array([low, high])
    return(res/N)

def gamma_brute2(tag_samples, tag):
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)
    c = 0.95
    low = gammainccinv(n, (1+c)/2)
    high = gammainccinv(n+1, (1-c)/2)
    res = np.array([low, high])
    return(res/N)

def gamma_brute3(tag_samples, tag):
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)
    c = 0.95
    low = gammaincinv(n, c/2)
    high = gammaincinv(n+1, 1-c/2)
    res = np.array([low, high])
    return(res/N)

def gamma_wiki(tag_samples, tag):
    N = len(tag_samples)
    n = np.sum(tag_samples == tag)
    c = 0.95
    low = gammainccinv(n, c/2)
    high = gammainccinv(n+1, 1-c/2)
    res = np.array([low, high])
    return(res/N)

def main():
    """ Example usage """
    start = datetime.datetime.now()
    duration = datetime.timedelta(2,0,0)
    end = start + duration
    tags = ['poop', 'food', 'play', 'sleep']
    mean_durations = [15, 45, 2*60, 6*60]
    activity_args = list(zip(tags, mean_durations))
    activities = [Activity(*arg) for arg in activity_args]
    schedule = RandomSchedule(start, end, activities)
    tag_percentages = schedule.get_tag_percentages()
    
    table = {}
    table['actual'] = tag_percentages

    ping_times = generate_sample_times(schedule.start, schedule.end, mean_interval=45)
    tag_samples = np.asarray([schedule.get_tag(time) for time in ping_times])

    methods = [
        wilson_score_interval,
        normal_approximation_interval,
        gamma_tom_jack,
        gamma_daniel_reeves,
        gamma_brute,
        gamma_brute2,
        gamma_brute3,
        gamma_wiki
    ]

    for method in methods:
        percentages = {}
        for tag in tags:
            percentages[tag] = list(method(tag_samples, tag))
        table[method.__name__] = percentages

    table_string = json.dumps(table, indent=4)

    print(table_string)

if __name__ == '__main__':
    main()

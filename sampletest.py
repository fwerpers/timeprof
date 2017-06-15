import datetime
import numpy as np
from schedule import Activity, RandomSchedule
import time

def get_random_interval(mean_interval):
    minutes = np.ceil(np.random.exponential(scale=mean_interval))
    duration = datetime.timedelta(0, minutes*60, 0)
    return(duration)

def generate_ping_times(start, end):
    mean_interval = 45
    times = [start]
    while True:
        duration = get_random_interval(mean_interval)
        next_time = times[-1] + duration
        if next_time > end:
            break
        times.append(next_time)

    return(times)

def main():
    """ Example usage """
    start = datetime.datetime.now()
    duration = datetime.timedelta(1,0,0)
    end = start + duration
    activity_args = [
        ('poop', 15),
        ('food', 45),
        ('play', 2*60),
        ('sleep', 6*60)
    ]
    activities = [Activity(*arg) for arg in activity_args]
    schedule = RandomSchedule(start, end, activities)
    tag_percentage = schedule.get_percentage()
    print(tag_percentage)

    ping_times = generate_ping_times(schedule.start, schedule.end)

    tags = np.asarray([schedule.get_tag(time) for time in ping_times])
    print(len(tags))
    print(tags)

if __name__ == '__main__':
    main()

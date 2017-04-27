import datetime
import numpy as np
import random

class RandomSchedule:
    def __init__(self, start, end, tags):
        ntags = len(tags)
        task_list = [Task(start, start+get_random_duration(), random.choice(tags))]
        while (task_list[-1].end < end):
            last_task = task_list[-1]
            rand_tag = random.choice(tags)
            new_task = Task(last_task.end, last_task.end + get_random_duration(), rand_tag)
            task_list.append(new_task)

        self.task_list = task_list

    def get_tag(self, time):
        i = 0;
        while (task_list[i].start < time):
            i += 1

        return(task_list[i].tag)

    def get_percentage(self):
        d = {}
        for tag in tags:
            d[tag] = 0
        return(dict)

def get_random_duration():
    minutes = np.ceil(20*np.random.exponential(scale=1.3))
    return(datetime.timedelta(0, minutes*60, 0))

class Task(object):
    def __init__(self, start, end, tag):
        self.start = start
        self.end = end
        self.tag = tag

        @property
        def duration():
            return(end-start)

def main():
    start = datetime.datetime.now()
    duration = datetime.timedelta(1,0,0)
    tags = [
        'bajs',
        'mat',
        'sov'
    ]
    s = RandomSchedule(start, start+duration, tags)

if __name__ == '__main__':
    main()

import datetime
import numpy as np
import random

class RandomSchedule:
    def __init__(self, start, end, tags):
        """Create random schedule from:
        start -- start time (datetime.datetime)
        end -- end time (datetime.datetime)
        tags -- list of tags (list of strings)
        """
        ntags = len(tags)
        task_list = [Task(start, start+get_random_duration(), random.choice(tags))]
        while (task_list[-1].end < end):
            last_task = task_list[-1]
            rand_tag = random.choice(tags)
            new_task = Task(last_task.end, last_task.end + get_random_duration(), rand_tag)
            task_list.append(new_task)

        self.task_list = task_list
        self.tags = tags
        self.duration = end-start

    def get_tag(self, time):
        """Get the tag (string)
        of a task occupying a certain
        time (datetime.datetime)
        """
        i = 0;
        while (task_list[i].start < time):
            i += 1

        return(task_list[i].tag)

    def get_percentage(self):
        """Get the time percentage (float)
        for each tag in the schedule
        """
        d = {}
        for tag in self.tags:
            d[tag] = 0
        for task in self.task_list:
            d[task.tag] += task.duration.total_seconds()/self.duration.total_seconds()
        return(d)

def get_random_duration():
    """Get a duration (datetime.timedelta)
    from a exponential distribution
    """
    minutes = np.ceil(20*np.random.exponential(scale=1.3))
    return(datetime.timedelta(0, minutes*60, 0))

class Task:
    def __init__(self, start, end, tag):
        """Create task from:
        start -- start time (datetime.datetime)
        end -- end time (datetime.datetime)
        tag -- (string)
        """
        self.start = start
        self.end = end
        self.tag = tag
        self.duration = end-start

def main():
    start = datetime.datetime.now()
    duration = datetime.timedelta(1,0,0)
    tags = [
        'bajs',
        'mat',
        'sov'
    ]
    schedule = RandomSchedule(start, start+duration, tags)
    tag_percentage = schedule.get_percentage()
    print(tag_percentage)

if __name__ == '__main__':
    main()

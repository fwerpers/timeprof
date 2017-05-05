import datetime
import numpy as np
import random

#TODO Change name from Task to TimeSlot
#TODO Create Activity class with tag and mean duration

class Activity:
    def __init__(self, tag, mean_duration):
        """Create activity from:
        tag -- activity descriptor (string)
        mean_duration -- mean duration in minutes (float)
        """
        self.tag = tag
        self.mean_duration = mean_duration

    def get_random_duration(self):
        """Get a duration (datetime.timedelta)
        from the exponential distribution defined by
        this activity's mean duration
        """
        minutes = np.ceil(np.random.exponential(scale=self.mean_duration))
        duration = datetime.timedelta(0, minutes*60, 0)
        return(duration)

class RandomSchedule:
    def __init__(self, start, end, activities):
        """Create random schedule from:
        start -- start time (datetime.datetime)
        end -- end time (datetime.datetime)
        activities -- list of activities (Activity objects)
        """
        timeslot_list = []
        rand_activity = random.choice(activities)
        new_timeslot = TimeSlot(
            start,
            start + rand_activity.get_random_duration(),
            rand_activity
        )
        timeslot_list.append(new_timeslot)
        while (timeslot_list[-1].end < end):
            last_timeslot = timeslot_list[-1]
            rand_activity = random.choice(activities)
            new_timeslot = TimeSlot(
                last_timeslot.end,
                last_timeslot.end + rand_activity.get_random_duration(),
                rand_activity
            )
            timeslot_list.append(new_timeslot)

        self.timeslot_list = timeslot_list
        self.activities = activities
        self.duration = end-start

    def get_tag(self, time):
        """Get the tag (string)
        of a task occupying a certain
        time (datetime.datetime)
        """
        i = 0;
        while (self.timeslot_list[i].start < time):
            i += 1

        return(self.timeslot_list[i].activity.tag)

    def get_percentage(self):
        """Get the time percentage (float)
        for each tag in the schedule
        """
        d = {}
        for activity in self.activities:
            d[activity.tag] = 0
        for timeslot in self.timeslot_list:
            d[timeslot.activity.tag] += timeslot.duration.total_seconds()/self.duration.total_seconds()
        return(d)

class TimeSlot:
    def __init__(self, start, end, activity):
        """Create task from:
        start -- start time (datetime.datetime)
        end -- end time (datetime.datetime)
        tag -- (string)
        """
        self.start = start
        self.end = end
        self.activity = activity
        self.duration = end-start

def main():
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

if __name__ == '__main__':
    main()

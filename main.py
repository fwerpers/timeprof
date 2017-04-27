import numpy as np
from matplotlib import pyplot as plt

def main():
    x = 20*np.ceil(np.random.exponential(scale=1.3, size=1000))
    plt.hist(x, bins='auto')
    plt.show()

if __name__ == '__main__':
    main()

import argparse

class ArgumentException(Exception):
    pass

class NonExitingArgParser(argparse.ArgumentParser):
    def error(self, message):
        raise ArgumentException(message)

def main3():
    parser = NonExitingArgParser()
    args = parser.parse_args("".split())
    print(args)
    print(dir(args))
    print(vars(args))

def main2():
    parser = NonExitingArgParser(prog="set rate", add_help=False)
    parser.add_argument("rate", type=float)
    try:
        #args = parser.parse_args(["-h", "5"])
        args = parser.parse_args(["-h", "5"])
    except ArgumentException as e:
        print("parsing failed")
        print(e)
    #print(parser._actions)
    #print(parser._action_groups)
    #print(parser._positionals)
    #print(parser._get_positional_actions())

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("rate", type=float)
    try:
        args = parser.parse_args("fasdf")
    except SystemExit as e:
        print("hjeje")
        print(e)
    print(parser)

if __name__ == "__main__":
    #main()
    main2()
    #main3()

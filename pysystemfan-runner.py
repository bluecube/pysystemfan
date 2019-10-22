#!/usr/bin/env python3

from pysystemfan import controler
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Fan manager.')
    parser.add_argument("--config", "-c", default=None,
                        help="where to look for the config file")
    args = parser.parse_args()

    controler.Controler(args.config).run()
else:
    raise Exception("Don't import this file, it's just a runner.")

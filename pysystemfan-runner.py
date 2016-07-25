#!/usr/bin/env python3

from pysystemfan import controler

if __name__ == "__main__":
    controler.Controler().run()
else:
    raise Exception("Don't import this file, it's just a runner.")

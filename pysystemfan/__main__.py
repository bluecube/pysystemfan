from . import pysystemfan

if __name__ == "__main__":
    psf = pysystemfan.PySystemFan()
    print(psf.dump_params())

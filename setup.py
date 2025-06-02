from setuptools import setup, find_packages

setup(
    name="yafs-fog-computing",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "simpy",
        "pandas",
        "networkx",
        "numpy",
        "tqdm",
        "matplotlib",
        "pulp",
        "shapely",
        "pyproj",
    ],
)

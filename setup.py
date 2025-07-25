from setuptools import setup, find_packages

setup(
    name="yafs-fog-computing",
    version="0.2.0",
    description="",
    author="Hafid Nur",
    author_email="hafidnurazis@gmail.com",
    url="https://github.com/hafidnrzs/yafs-fog-computing",
    package_dir={"": "."},
    packages=find_packages(include=["yafs*"]),
    python_requires=">=3.6",
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
        "scipy",
        "smopy",
        "ipykernel",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)

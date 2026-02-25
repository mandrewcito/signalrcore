import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="signalrcore",
    version="1.0.2",
    author="mandrewcito",
    author_email="signalrcore@mandrewcito.dev",
    description="Python SignalR Core full client (transports and encodings)."
    "Compatible with azure / serverless functions."
    "Also with automatic reconnect and manually reconnect.",
    keywords="signalr core client 3.1+",
    long_description=long_description,
    long_description_content_type="text/markdown",
    license_file="LICENSE",
    url="https://github.com/mandrewcito/signalrcore",
    packages=setuptools.find_packages(exclude=["test", "test.*"]),
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent"
    ],
    install_requires=[
        "msgpack==1.1.2"
    ],
    extras_require={
        'dev': [
            'requests',
            'flake8',
            'coverage',
            'pytest',
            'pytest-cov',
            'build'
        ]
    },
    project_urls={
        "Homepage": "https://signalrcore.mandrewcito.dev",
        "Documentation": "https://mandrewcito.github.io/signalrcore/",
        "Repository": "https://github.com/mandrewcito/signalrcore",
        "Tracker": "https://github.com/mandrewcito/signalrcore/issues",
        "Changelog": "https://github.com/mandrewcito/signalrcore/releases",
    }
)

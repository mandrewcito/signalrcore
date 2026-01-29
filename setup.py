import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="signalrcore",
    version="1.00.00a",
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
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3.8",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent"
    ],
    install_requires=[
        "msgpack==1.0.2"
    ],
    extras_require={
        'dev': [
            'requests',
            'flake8',
            'coverage',
            'pytest',
            'pytest-cov'
        ]
    },
)

# demo for quickfix (python)

This repo will generate nice quickfix message class(use dataclass) like how C++ bindings does. But the performance is bad in runtime(due to runtime tag check and conversion). If you want know how to use quickfix, look at [quickfix-python-samples](https://github.com/rinleit/quickfix-python-samples)

- [build.py](./build.py) script to generate python code
- [server.py](./server.py) server script
- [client.py](./client.py) client script

## how to setup
```bash
# on linux
conda install -c conda-forge quickfix # or python -m pip install quickfix
conda install click # used in example
```

## how to use
```bash
# python3.8
cd .

mkdir -p logs sessions

# generate message objects
python build.py

# startup server
python server.py -c server.cfg

# startup client
python client.py -c client.cfg
```

# demo for quickfix(python)

This repo will generate nice quickfix message class(use attr) like how C++ bindings does. But the performance is bad in
runtime(lots of if/loop).

## how to setup
```bash
# on linux
conda install -c conda-forge quickfix
conda install attrs, click
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

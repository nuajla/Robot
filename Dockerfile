FROM python:3.10-slim

WORKDIR /workspace

# Kopiraj robotblockset in instaliraj
COPY robotblockset_python-master-2026-04/robotblockset_python-master/ ./robotblockset_python-master/
RUN pip install ./robotblockset_python-master

# Kopiraj tvoje skripte
COPY *.py ./

RUN pip install ipython
RUN pip install panda-python
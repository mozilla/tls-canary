#/bin/bash

brew ls --versions openssl || brew install openssl
brew ls --versions libffi || brew install libffi
brew ls --versions python || brew install python
brew ls --versions p7zip || brew install p7zip
brew ls --versions go || brew install go

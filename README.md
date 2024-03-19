# anthroprompter

Inefficient personal tool for interacting with Claude from console. Inefficient because input data is for now not cleaned and thus more tokens are sent than necessary including HTML stuff.

# Use

For now you need to clone it and install the relevant packages. Usage below.

```
usage: main.py [-h] -i INPUT [-o OUTPUT] [--system SYSTEM] [--model MODEL] [--ddepth DDEPTH] [-t TEMPERATURE]

A python program for local interaction with Anthropic's API. You can download websites and pass them right to one of Anthropic's models.

options:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input file path. The input file must be formatted as "PROMPT" WEBSITE_1 WEBSITE_2 WEBSITE_3 ... Each website in order and all
                        child links up to some depth will be downloaded and appended to the prompt which will be sent to Anthropic's servers for
                        inference.
  -o OUTPUT, --output OUTPUT
                        Output file path, if nothing is specified it will default to the inputs name + a suffix.
  --system SYSTEM       System prompt file path. It will automatically look for system.txt.
  --model MODEL         Specify the exact version of the model to use, otherwise the latest default Opus is used.
  --ddepth DDEPTH       Website download depth when recursing child links. I would recommend not setting it above 3 initially such that you don't eat up
                        15$ worth of tokens immediately :].
  -t TEMPERATURE, --temperature TEMPERATURE
                        Amount of randomness injected into the response. Defaults to 1.0. Ranges from 0.0 to 1.0. Use temperature closer to 0.0 for
                        analytical / multiple choice, and closer to 1.0 for creative and generative tasks.
```

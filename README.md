# anthroprompter

Inefficient personal tool for interacting with Claude from console. Inefficient because input data is for now not cleaned and thus more tokens are sent than necessary including HTML stuff.

## Use

For now you need to clone it and install the relevant packages.

Here is an example of how to use it.

We'll take the prompt:

```txt
Please describe the following website data:

https://en.wikipedia.org/wiki/Mind%E2%80%93body_problem

Please find the roots of the following polynomial:

poly.txt
```

```bash
# Definitely do this
echo "x^2 -4x + 3" > poly.txt

# If you didn't copy from above do this
echo "Please describe the following website data:\n\nhttps://en.wikipedia.org/wiki/Mind%E2%80%93body_problem\n\nPlease find the roots of the following polynomial:\n\npoly.txt" > input.txt

# Obviously do this
python main.py -i input.txt
```

This means, you can include links and files in your text and it will expand website and text data in place and pass it to Anthropic. It will inline it, so be careful how you structure your prompt.

Full cmd help below:

```
usage: main.py [-h] -i INPUT [-o OUTPUT] [-t TEMPERATURE] [--system SYSTEM] [--model MODEL] [--ddepth DDEPTH]

A python program for local interaction with Anthropic's API. You can download websites and pass them right to one of Anthropic's
models.

optional arguments:
  -h, --help            show this help message and exit
  -i INPUT, --input INPUT
                        Input file path. The input file may contain both links and filepaths, both are going to be expanded in
                        place, meaning that any website data is going to be expanded inline with text, and any filepath is going to
                        be expanded inline with text.
  -o OUTPUT, --output OUTPUT
                        Output file path, if nothing is specified it will default to the inputs name + a suffix.
  -t TEMPERATURE, --temperature TEMPERATURE
                        Amount of randomness injected into the response. Defaults to 1.0. Ranges from 0.0 to 1.0. Use temperature
                        closer to 0.0 for analytical / multiple choice, and closer to 1.0 for creative and generative tasks.
  --system SYSTEM       System prompt file path. It will automatically look for system.txt.
  --model MODEL         Specify the exact version of the model to use, otherwise the latest default Opus is used.
  --ddepth DDEPTH       Website download depth when recursing child links. I would recommend not setting it above 3 initially such
                        that you don't eat up 15$ worth of tokens immediately :].
```

## Next 

This will be used as the backbone module, a server running a jupyter kernel will be preload it and the idea is to expand it such that Anthropic (and in future other AI) calls can be made from notebooks.

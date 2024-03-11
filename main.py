import os
import re
import sys
import json
import requests
import argparse
import anthropic

from bs4 import BeautifulSoup
from dotenv import load_dotenv


def download_webpage_recursive(url, depth=3):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()

    if 1 < depth:
        base_url = url.split("//")[-1].split("/")[0]

        for link in soup.find_all("a"):
            href = link.get("href")

            if href:
                if href.startswith(("http://", "https://")) and base_url in href:
                    text += "\n\n" + download_webpage(href, depth - 1)
                elif href != "/" and not href.startswith(("http://", "https://")):
                    print(href)
                    text += "\n\n" + download_webpage(
                        "http://" + base_url + href, depth - 1
                    )
    return text


def extract_inputs(input_string):
    pattern = r'"(.*?)"((?:\s+\S+)*)'
    match = re.match(pattern, input_string)

    if match:
        text = match.group(1)
        urls = match.group(2).split()
        result = [text] + urls
        return result
    else:
        return None


def main(args):
    # Prep environment

    current_dir = os.getcwd()

    load_dotenv()

    # Variables

    claude_model = os.getenv("CLAUDE_MODEL") or args.model

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not anthropic_api_key:
        print("\nAn Anthropic API key must be specified in .dotenv, exiting!\n")
        sys.exit(0)

    input_file_name = args.input

    system_prompt_file_name = args.system

    prompt_file_path = f"{os.path.splitext(input_file_name)[0]}_prompt.txt"

    answer_file_path = (
        os.path.join(current_dir, args.output)
        if args.output
        else f"{os.path.splitext(input_file_name)[0]}_answer.txt"
    )

    # Extract input data

    extracted_inputs = []

    with open(os.path.join(current_dir, input_file_name), "r") as file:
        extracted_inputs = extract_inputs(file.read().strip())

    user_prompt = extracted_inputs[0]

    urls = extracted_inputs[1:]

    # Prepare system prompt text

    system_prompt = ""

    system_prompt_file_path = os.path.join(current_dir, system_prompt_file_name)

    if os.path.isfile(system_prompt_file_path):
        with open(system_prompt_file_path, "r") as file:
            system_prompt = file.read().strip()

    # Download webpages and collect all of the data

    appended_data = ""

    for url in urls:
        appended_data += download_webpage_recursive(url, args.ddepth) + "\n"

    # Construct final prompt

    final_prompt = f"{user_prompt}\n\n{appended_data}"

    # First record what was prompted

    with open(prompt_file_path, "w") as file:
        file.write(final_prompt)

    # Then request inference from Anthropic's servers

    client = anthropic.Client(api_key=anthropic_api_key)

    response = client.messages.create(
        messages=[{"role": "user", "content": final_prompt}],
        temperature=args.temperature,
        system=system_prompt,
        model=claude_model,
        max_tokens=4096,
    )

    # Collect all answers

    response_text = " ".join(
        [content.text for content in response.content if content.type == "text"]
    )

    # Then finally record the answer

    with open(answer_file_path, "w") as file:
        file.write(response_text)

    print(f"Answer saved to {answer_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A python program for local interaction with Anthropic's API. You can download websites and pass them right to one of Anthropic's models."
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help='Input file path. The input file must be formatted as "PROMPT" WEBSITE_1 WEBSITE_2 WEBSITE_3 ... Each website in order and all child links up to some depth will be downloaded and appended to the prompt which will be sent to Anthropic\'s servers for inference.',
        type=str,
    )

    parser.add_argument(
        "-o",
        "--output",
        required=False,
        help="Output file path, if nothing is specified it will default to the inputs name + a suffix.",
        type=str,
    )

    parser.add_argument(
        "--system",
        required=False,
        help="System prompt file path. It will automatically look for system.txt.",
        default="system.txt",
        type=str,
    )

    parser.add_argument(
        "--model",
        required=False,
        type=str,
        help="Specify the exact version of the model to use, otherwise the latest default Opus is used.",
        default="claude-3-opus-20240229",
    )

    parser.add_argument(
        "--ddepth",
        required=False,
        help="Website download depth when recursing child links. I would recommend not setting it above 3 initially such that you don't eat up 15$ worth of tokens immediately :].",
        default=1,
        type=int,
    )

    parser.add_argument(
        "-t",
        "--temperature",
        required=False,
        help="Amount of randomness injected into the response. Defaults to 1.0. Ranges from 0.0 to 1.0. Use temperature closer to 0.0 for analytical / multiple choice, and closer to 1.0 for creative and generative tasks.",
        default=0,
        type=float,
    )

    main(parser.parse_args())

import os
import re
import sys
import json
import requests
import argparse
import anthropic

from bs4 import BeautifulSoup
from dotenv import load_dotenv


def prepare_prompt(prompt):
    # Remove comments from Python code
    prompt = re.sub(r"#.*", "", prompt)

    prompt = re.sub(r'""".*?"""', "", prompt, flags=re.DOTALL)

    # Remove unnecessary spaces around punctuation
    prompt = re.sub(r"\s*([.,;:!?])\s*", r"\1 ", prompt)

    # Remove unnecessary spaces before and after parentheses, brackets, and braces
    prompt = re.sub(r"\s*([(){}\[\]])\s*", r"\1", prompt)

    # Remove unnecessary spaces around operators
    prompt = re.sub(r"\s*([+\-*/%=<>])\s*", r" \1 ", prompt)

    # Remove extra whitespace and newline characters
    # prompt = re.sub(r'\s+', ' ', prompt)

    # Remove leading/trailing whitespace
    prompt = prompt.strip()

    return prompt


def is_valid_file(file):
    return os.path.isfile(os.path.abspath(file))


def read_file_contents_recursive(path, depth=1, current_depth=0, relative_path=""):
    contents = ""

    if current_depth == 0:
        relative_path = path
        path = os.path.abspath(path)

    if os.path.isfile(path):
        prefix = f"\n\n{relative_path}:\n\n" if current_depth != 0 else ""
        try:
            with open(path, "r", encoding="utf-8") as file:
                contents += prefix + f"{file.read().strip()}\n\n"
        except FileNotFoundError:
            raise FileNotFoundError(f"\nFile {path} not found")

    elif os.path.isdir(path):
        for item in os.listdir(path):
            item_path = os.path.join(path, item)
            item_relative_path = os.path.join(relative_path, item)

            if os.path.isfile(item_path):
                contents += read_file_contents_recursive(
                    item_path, depth, current_depth + 1, item_relative_path
                )

            elif os.path.isdir(item_path) and current_depth < depth:
                contents += read_file_contents_recursive(
                    item_path, depth, current_depth + 1, item_relative_path
                )
    else:
        raise Exception(
            f"\nProgram should not have reached this point, {path} is not a file nor dir."
        )

    return contents


def download_webpage_recursive(url, depth=1):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text()

    if 1 < depth:
        base_url = url.split("//")[-1].split("/")[0]

        for link in soup.find_all("a"):
            href = link.get("href")

            if href:
                if href.startswith(("http://", "https://")) and base_url in href:
                    text += (
                        "\n\n"
                        + href
                        + ":\n\n"
                        + download_webpage_recursive(href, depth - 1)
                        + "\n\n"
                    )
                elif href != "/" and not href.startswith(("http://", "https://")):
                    url = "http://" + base_url + href
                    text += (
                        "\n\n"
                        + url
                        + ":\n\n"
                        + download_webpage_recursive(url, depth - 1)
                        + "\n\n"
                    )
    return text


def main(args):
    # Prep environment

    load_dotenv()

    # Prepare system prompt text

    system_prompt = ""

    if is_valid_file(args.system):
        system_prompt = read_file_contents_recursive(args.system)
        print(f"\nSystem prompt {args.system} is being used!")

    # Prompt construction

    if not os.path.exists(args.input):
        print(f"\nFile or directory {args.input} does not exist, exiting!")
        sys.exit(0)

    extracted_inputs = []

    # This will always be a normal file, not a dir

    raw_input = read_file_contents_recursive(args.input)

    # Split into parts which we can check

    input_parts = re.split(r"(\s+)", raw_input)

    for part in input_parts:
        # If URL, download recursively
        if part.startswith(("http://", "https://")):
            if not args.urls or part in args.urls:
                extracted_inputs.append(
                    download_webpage_recursive(part.strip(), args.ddepth)
                )
        # If file or dir, read or recursively read
        elif os.path.exists(part):
            if not args.files or part in args.files:
                extracted_inputs.append(
                    read_file_contents_recursive(part.strip(), args.fdepth)
                )
        else:
            # Read
            extracted_inputs.append(part)

    final_prompt = (
        prepare_prompt("".join(extracted_inputs))
        if args.clean
        else "".join(extracted_inputs)
    )

    # First record what was prompted

    prompt_file_path = f"{os.path.splitext(args.input)[0]}_prompt.txt"

    with open(prompt_file_path, "w", encoding="utf-8") as file:
        file.write(final_prompt)

    print(f"\nFinal prompt written to {prompt_file_path}")

    # Then request inference from Anthropic's servers

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not anthropic_api_key:
        print("\nAn Anthropic API key must be specified in .dotenv, exiting!")
        sys.exit(0)

    client = anthropic.Client(api_key=anthropic_api_key)

    claude_model = os.getenv("CLAUDE_MODEL") or args.model

    print("\nSending prompt to Anthropic servers.")

    response = client.messages.create(
        messages=[{"role": "user", "content": final_prompt}],
        temperature=args.temperature,
        system=system_prompt,
        model=claude_model,
        max_tokens=4096,
    )

    print("\nServer responded with message.")

    # Collect all answers

    response_text = " ".join(
        [content.text for content in response.content if content.type == "text"]
    )

    # Then finally record the answer

    answer_file_path = (
        os.path.abspath(args.output)
        if args.output
        else os.path.abspath(os.path.splitext(args.input)[0] + "_answer.txt")
    )

    with open(answer_file_path, "w", encoding="utf-8") as file:
        file.write(response_text)

    print(f"\nAnswer saved to {answer_file_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="A python program for local interaction with Anthropic's API. You can download websites and pass them right to one of Anthropic's models."
    )

    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Input file or directory path. The input file may contain both links and filepaths, both are going to be expanded in place, meaning that any website data is going to be expanded inline with text, and any filepath is going to be expanded inline with text.",
        type=str,
    )

    parser.add_argument(
        "-f",
        "--files",
        nargs="+",
        required=False,
        help="Sometimes it is necessary to specify which files should exactly be inlined for the reason that any file names may theoretically expanded by the program. This is not required but your inlines will silently fail if you do not set this. It can be a whitespace separated list of filenames.",
        type=str,
    )

    parser.add_argument(
        "-u",
        "--urls",
        nargs="+",
        required=False,
        help="Sometimes it is necessary to specify which urls should exactly be inlined for the reason that any urls may theoretically expanded by the program. This is not required but your inlines will silently fail if you do not set this. It can be a whitespace separated list of urls.",
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
        "-t",
        "--temperature",
        required=False,
        help="Amount of randomness injected into the response. Defaults to 1.0. Ranges from 0.0 to 1.0. Use temperature closer to 0.0 for analytical / multiple choice, and closer to 1.0 for creative and generative tasks.",
        default=0,
        type=float,
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
        help="Website download depth when recursing child links. I would recommend not setting it above 3 initially such that you don't eat up 15$ worth of tokens immediately :]. Defaults to 1, meaning it will only download the website at the URL and not recurse into other hrefs.",
        default=1,
        type=int,
    )

    parser.add_argument(
        "--fdepth",
        required=False,
        help="File and directory recursion depth when reading files. Defaults to 1, meaning it will only read files in the specified directory and not recurse into subdirectories.",
        default=1,
        type=int,
    )

    parser.add_argument(
        "--clean",
        required=False,
        action="store_true",
        default=False,
        type=bool,
        help="Set flag to clean input to reduce token size. Check function on how it does it for now.",
    )

    main(parser.parse_args())

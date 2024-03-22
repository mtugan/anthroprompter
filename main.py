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


def expand_references(prompt, args):
    input_parts = re.split(r"(\s+)", prompt)
    extracted_inputs = []

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

    if args.clean:
        final_prompt = prepare_prompt("".join(extracted_inputs))
    else:
        final_prompt = "".join(extracted_inputs)

    return final_prompt


def query_anthropic(prompt, anthropic_model, system_prompt, tokens):
    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

    if not anthropic_api_key:
        print("\nAn Anthropic API key must be specified in .dotenv, exiting!")
        sys.exit(0)

    # Abstract this out into class variable
    client = anthropic.Client(api_key=anthropic_api_key)

    response = client.messages.create(
        messages=[{"role": "user", "content": prompt}],
        model=anthropic_model,
        system=system_prompt,
        max_tokens=tokens,
    )

    return " ".join(
        [content.text for content in response.content if content.type == "text"]
    )


def query_anthropic_enhance_prompt(prompt):
    system_prompt = read_file_contents_recursive("assistants/00-prompt.txt")
    return query_anthropic(prompt, "claude-3-opus-20240229", system_prompt, 4096)


def replace_path_suffix(path, suffix):
    return f"{os.path.splitext(path)[0]}{suffix}"


def save_to_file(data, path, message):
    with open(path, "w", encoding="utf-8") as file:
        file.write(data)
    print("\n" + message)


def main(args):
    # Prep environment
    load_dotenv()

    # Prepare system prompt text
    system_prompt = ""
    prompt_enhancement = False

    if args.enhance:
        # Use default system prompt and model for prompt enhancement
        prompt_enhancement = True

    if args.system and is_valid_file(args.system):
        system_prompt = read_file_contents_recursive(args.system)
        print(f"\nSystem prompt {args.system} is being used!")

    # Prompt construction
    if not os.path.exists(args.input):
        print(f"\nFile or directory {args.input} does not exist, exiting!")
        sys.exit(0)

    extracted_inputs = []

    # This will always be a normal file, not a dir
    raw_input = read_file_contents_recursive(args.input)

    if prompt_enhancement:
        print("\nEnhancing prompt!")

        # Enhance the prompt using the default system prompt and model
        enhanced_prompt = query_anthropic_enhance_prompt(raw_input)

        enhanced_prompt_file_path = replace_path_suffix(
            args.input, "_enhanced_prompt.txt"
        )

        save_to_file(
            enhanced_prompt,
            enhanced_prompt_file_path,
            f"\nEnhanced prompt written to {enhanced_prompt_file_path}",
        )

        final_prompt = expand_references(enhanced_prompt, args)
    else:
        # Use the raw input as the final prompt if --model is specified
        final_prompt = expand_references(raw_input, args)

    # First record what was prompted
    prompt_file_path = replace_path_suffix(args.input, "_prompt.txt")

    save_to_file(
        final_prompt, prompt_file_path, f"\nFinal prompt written to {prompt_file_path}"
    )

    # Then request inference from Anthropic's servers

    print("\nSending prompt to Anthropic servers.")
    response_text = query_anthropic(
        final_prompt, args.model or "claude-3-haiku-20240307", system_prompt, 4096
    )
    print("\nServer responded with message.")

    # Then finally record the answer
    answer_file_path = ""

    if args.output:
        answer_file_path = os.path.abspath(args.output)
    else:
        answer_file_path = replace_path_suffix(args.input, "_answer.txt")

    save_to_file(
        response_text, answer_file_path, f"\nAnswer saved to {answer_file_path}"
    )


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
        "--enhance",
        required=False,
        action="store_true",
        default=False,
        help="Whether to enhance with Opus and then pass to a model or just to pass it to a model.",
    )

    parser.add_argument(
        "--model",
        required=False,
        type=str,
        help="Specify the exact version of the model to use, otherwise the latest default Opus is used.",
        default="",
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
        help="Set flag to clean input to reduce token size. Check function on how it does it for now.",
    )

    main(parser.parse_args())

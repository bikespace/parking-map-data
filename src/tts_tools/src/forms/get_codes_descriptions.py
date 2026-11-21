from pathlib import Path

from bs4 import BeautifulSoup


def get_codes_descriptions(file: Path) -> list[tuple[str, str]]:
    """
    Extracts code and description values from the html source for a https://drs.dmg.utoronto.ca/idrs/ttsForm/Cros/ form.

    E.g.

    ```html
    <option data-backend="rec_mail">Receipt of advance letter</option>
    ```

    becomes:

    ```python
    ("rec_mail", "Receipt of advance letter")
    ```

    And the full set is returned as a list of tuples.
    """
    text = file.read_text()

    soup = BeautifulSoup(text, "html.parser")

    options = soup.find_all("option", attrs={"data-backend": True})
    results = [
        (option.attrs["data-backend"], option.text.strip()) for option in options
    ]
    return results


def main():
    """
    Extracts code and description values from the specified folder of html source pages using `get_codes_descriptions` and saves them to a text file wit a custom format per line.
    """
    pages = Path("src/tts_tools/src/forms/pages").glob("*.html")

    results = []
    for page in pages:
        cd = get_codes_descriptions(page)
        results.extend(cd)

    formatted = [f'"{code}": "{description}",' for code, description in results]

    output_path = Path("src/tts_tools/src/forms/c_d_options.txt")
    output_path.write_text("\n".join(formatted))


if __name__ == "__main__":
    main()

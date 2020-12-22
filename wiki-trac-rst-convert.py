# Convert local files formated in Trac Wiki RST to Vanilla RST.
import sys
import os

def main():
    """
    Do the job.
    """
    if len(sys.argv) != 2:
        print("Need to pass the path to wiki base directory.")
        sys.exit(1)

    for root, _, files in os.walk(sys.argv[1]):
        for name in files:
            convert_file(os.path.join(root, name))


def convert_file(path):
    """
    """
    print('Converting ', path)


def convert_content(text):
    """
    Conver from Trac wiki RST format to standard RST format.
    """
    # Remove RST wrapping.
    result = text.strip('}}}')
    result = result.strip('{{{')
    result = result.strip()
    result = result.strip('#!rst')
    result += '\n'

    return result


if __name__ == '__main__':
    main()

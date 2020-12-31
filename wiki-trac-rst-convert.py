# Convert local files formated in Trac Wiki RST to Vanilla RST.
import sys
import os

wiki_url = 'https://github.com/chevah/server/wiki/'
git_url = 'https://github.com/chevah/server/wiki/'

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
    file = open(path, "r")
    text = file.readlines()
    convert_content(text, path)

def convert_content(text, path):
    """
    Convert from Trac wiki RST format to standard RST format.
    """
    title_index = 'TitleIndex'
    formatted_rst_text = ''
    for line in text:
        # Remove RST wrapping.
        result = line.strip('}}}')
        result = result.strip('{{{')
        result = result.strip('#!rst')
        result = result.strip()

        result = result.replace(':trac:', '')
        result = result.replace('`', '')
        result = result.replace('*', '')
        result = result.strip()

        if '[http:' in result:
            result = result.replace('[', '')
            result = result.replace(']', '')
            result = handle_http_urls(result)
        else:
            result = result.replace('[', '')
            result = result.replace(']', '')
            if result is not '':
                result = result.replace('wiki:', '<' +wiki_url)
                words = result.split(' ')

                if wiki_url in words[0] and len(words) > 1:
                    re_do_text = ''
                    for word in words[1:]:
                        re_do_text = re_do_text + word + ' '
                    result = words[0] + '>`_ ' + re_do_text
                elif wiki_url in words[0]:
                    result = result + '>`_'
                elif git_url in result: 
                    result  = handle_git_urls(words)

        if wiki_url in result:
            a = result.split('>')
            formated_name = ''
            formated_name = format_name(a[0])
            result = '* `' + formated_name + ' ' + result + '\n\n'
        
        if not result == '':
            if result[-1] == '=':
                result += '\n\n\n'
            else:
                result += '\n\n'

        if title_index in result:
            result = write_sub_links(result, path)

        formatted_rst_text = formatted_rst_text + result

    return formatted_rst_text

def write_sub_links(text, path):
    find_brackets_index = text.find('(')
    find_slash_index = text.find('/')

    sub_links_title = text[find_brackets_index +1:find_slash_index] 
    path = '../server.wiki/' + sub_links_title

    link = ''
    sub_links = ''

    for subdir, dirs, files in os.walk(path):
        for file in files:
            link = file.replace('.rst', '')
            link = link.replace(' ', '-')
            name = link.replace(link+'-', '')
            sub_links = sub_links + '* ' + '`'+ name + ' <' + wiki_url + link + '>`_\n'

    return sub_links

def format_name(text):
    """
       Format Wiki name 
    """

    name = text.split('/')
    return name[-1]

def handle_http_urls(text):
    """
        Format http urls for standart rst
    """
    words = text.split(' ')
    url = words[0]
    plain_text = ''
    for data in words[1:]:
        plain_text = plain_text + data + ' '
    words = ' <' + url + '>'
    formatted_text =  '* `' + plain_text + words + '`_\n'

    return formatted_text

def handle_git_urls(text_arr):
    formatted_text = ''
    for string in text_arr:
        if git_url in string:
            string += '>`_'
            formatted_text = formatted_text + string
        else:
            formatted_text = formatted_text + string +  ' '

    return formatted_text

if __name__ == '__main__':
    main()


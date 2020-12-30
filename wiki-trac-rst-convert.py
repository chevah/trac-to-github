# Convert local files formated in Trac Wiki RST to Vanilla RST.
import sys
import os


wiki_url = 'https://github.com/chevah/server/wiki/'


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
    if 'Administrative.rst' in path:    
        file = open(path, "r")
        text = file.readlines()
        convert_content(text, path)



def convert_content(text, path):
    """
    Convert from Trac wiki RST format to standard RST format.
    """
    #import pdb; import sys; sys.stdout = sys.__stdout__; pdb.set_trace()

    title_index = '[[TitleIndex'

    string1 = ''
    for line in text:

        # Remove RST wrapping.
        result = line.strip('}}}')
        result = result.strip('{{{')
        result = result.strip('#!rst')
        result = result.strip()


        result = result.replace(':trac:`', '')
        #only for main pagess
        if '[wiki:' not in result:
            result = result.replace('wiki:', '(' + wiki_url)
        
        result = result.replace('`', ')')
        result = result.replace('*', '')
        result = result.strip()

        if wiki_url in result:

            a = result.split(wiki_url)
            format_link = a[1].replace(')', '')
            result = '* [' + format_link +']' + result
        
        
        result += '\n'
        if title_index in result:
            result = write_sub_links(result, path)

        string1 = string1 + result

    return string1# Convert local files formated in Trac Wiki RST to Vanilla RST.
import sys
import os


wiki_url = 'https://github.com/chevah/server/wiki/'


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
    if 'Administrative.rst' in path:    
        file = open(path, "r")
        text = file.readlines()
        convert_content(text, path)



def convert_content(text, path):
    """
    Convert from Trac wiki RST format to standard RST format.
    """
    #import pdb; import sys; sys.stdout = sys.__stdout__; pdb.set_trace()

    #`Requirements <https://github.com/chevah/server/wiki/Requirements>`_

    title_index = '[[TitleIndex'

    string1 = ''
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

        if '[wiki:' in result:
            result = result.replace('[wiki:', ' ` ' + wiki_url)
            result = result.replace(']', '')
        #only for main pagess
        else:
            if result is not '':
                result = result.replace('wiki:', '<' +wiki_url)
                abcd = result.split(' ')

                if wiki_url in abcd[0] and len(abcd) > 1:
                    aaaaa = ''
                    for string in abcd[1:]:
                        aaaaa = aaaaa + string + ' '
                    result = abcd[0] + '>`_ ' + aaaaa

                elif wiki_url in abcd[0]:
                    result = result + '>`_'

        if wiki_url in result:
            a = result.split('>')
            formated_name = ''
            formated_name = format_name(a[0])

            result = '* `' + formated_name + ' ' + result
            #if result[-1] == ".":
            #    result = result + '`'

        result += '\n'
        if title_index in result:
            result = write_sub_links(result, path)

        string1 = string1 + result

    
    f = open("myfile.rst", "w") 

    f.write(string1)
    f.close()


    #return result


def write_sub_links(text, path):
   # import pdb; import sys; sys.stdout = sys.__stdout__; pdb.set_trace()

    result = text.replace('[[TitleIndex(', '')
    result = result.replace('/)]]', '')
    result = result.strip()
    path = '../server.wiki/' + result

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

    q = text.split('/')
    print(q[-1])
    return q[-1]


if __name__ == '__main__':
    main()


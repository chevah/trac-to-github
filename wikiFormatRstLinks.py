#Format links in rst files.
#For RST, only the links are converted, everything else is kept as it is

wiki_url = 'https://github.com/chevah/server/wiki/'


def convert_links(text):
    """
    Convert rst links 
    """

    formatted_text = ''

    for line in text:
        result = line.strip('}}}')
        result = result.strip('{{{')
        result = result.replace('[[PageOutline]]', '')
        result = result.strip('#!rst')
        result = result.replace(':trac:', '')        

        find_first_apostrophe = result.find('`')
        if find_first_apostrophe != -1:
            after_first_apostrophe = result[find_first_apostrophe+1:] 
            find_second_apostrophe = after_first_apostrophe.find('`')
            between_apostrophes = after_first_apostrophe[:find_second_apostrophe]
            formatted_link = format_link(between_apostrophes)
            result = result[:find_first_apostrophe] + formatted_link + after_first_apostrophe[find_second_apostrophe + 1:]

        formatted_text = formatted_text + result

    return formatted_text


def format_link(sentence):
    """
    Format wiki links for rst
    """
    result = sentence.replace(':trac:', '')
    result = result.replace('wiki:', '<' +wiki_url)

    inline_link = ''
    words = result.split(' ')

    if wiki_url in words[0]:
        link = words[0] + '>'
        
        for word in words[1:]:
            inline_link = inline_link + word + ' '        

        inline_link = '`' + inline_link + link + '`_'

        return inline_link
    
    return '`' + sentence + '`_'

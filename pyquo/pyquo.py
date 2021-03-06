#!/usr/bin/python3

import os
import re
import sys
import json
import arrow
import argparse
import markdown
import unicodedata
from pyquo import utils
from pprint import pprint
from subprocess import Popen
from datetime import datetime
from bs4 import BeautifulSoup
from collections import namedtuple

EPILOG = """
Set properties in {}
""".format(utils.DEFAULT_PROPERTIES_FILE)


def generate_pages(properties):
    proj_root = properties.get('root', '/')
    homepage = properties.get('homepage', 'index.html')
    searchpage = properties.get('searchpage', 'search.html')
    site_title = properties.get('site_title', 'PyQuo')
    ts_frmt = properties.get('timestamp_format', 'dddd DD MMMM, YYYY')
    directory = properties.get('source_directory', 'markdown')
    media_directory = properties.get('media_directory', 'media')
    css = properties.get('css')
    entries_to_show = properties.get('entries_to_show', 10)
    parser = properties.get('beautiful_soup_parser', 'lxml')

    all_pages = []
    categories = []
    count = 0

    for root, dirs, files in os.walk(directory):
        valid_files = [file for file in files if not
                       (file.endswith('~') or file.startswith('.'))]

        for valid_file in valid_files:
            with open(os.path.join(root, valid_file), 'r') as input_file:
                md = markdown.Markdown(extensions=['markdown.extensions.meta'])
                markdown_text = input_file.read()
                html = md.convert(markdown_text)
                text = ''.join(BeautifulSoup(html, parser).findAll(text=True))
            if md.Meta == {}:
                continue

            meta = namedtuple('meta', [])
            meta.title = md.Meta['title'][0]
            meta.slug = utils.slugify(meta.title)
            meta.categories = [
                category for category in set([cat.replace(" ", "").lower()
                for cat in md.Meta['category'][0].split(',')])]
            meta.authors = md.Meta['authors'][0]
            meta.date = md.Meta['date'][0]
            meta.tags = md.Meta['tags'][0].split(',')
            meta.header_image = md.Meta['headerimage'][0]
            meta.publish = True if md.Meta['publish'][0].lower() in [
                'true', 'yes'] else False
            meta.content = html
            meta.index = re.findall("\w+", text.lower())
            categories.extend(meta.categories)

            if meta.publish is True:
                generate_static_page(site_title, homepage, searchpage, meta,
                                     css, ts_frmt, proj_root)
                all_pages.append(meta)
                count += 1
        all_cats = [category for category in set(categories)]
        print('{} pages generated with the following categories: {}.'
              .format(count, ', '.join(all_cats)))
        all_cats, tags, chronology, index, word_cloud =\
            extract_site_wide_metadata(all_pages)
        generate_front_and_category_pages(site_title, homepage, searchpage, all_cats, tags,
                            chronology, word_cloud, proj_root, css, ts_frmt,
                            entries_to_show)
        generate_search_page(site_title, homepage, searchpage, index, css,
                             proj_root)


def extract_site_wide_metadata(all_pages, key='index_and_tags',
                               ignore_threshold_percentage=40):
    """Get site-wide metadata.

    - Arrange titles by inverse date order, with link to location.
    - Generate tag cloud (dict of tag and number of times used).
    - Generate calendar so can click on a date and get link.
    """

    categories = []
    tags = {}
    chronology = {}
    index = {}
    for page in all_pages:
        for cat in page.categories:
            category = cat.lower()
            if category not in categories:
                categories.append(category)

            for _tag in page.tags:
                tag = _tag.strip().lower()
                if tag not in tags:
                    tags[tag] = 1
                else:
                    tags[tag] += 1


            if page.date not in chronology:
                link = "{}/{}.html".format(category, page.slug)

                if page.date != '':
                    timestamp = arrow.get(page.date)
                else:
                    timestamp = arrow.now()
                add_to_chronology_dict(
                    chronology, category, timestamp, (page.title, link))

            tags_only = [tag.lower().strip() for tag in page.tags if tag != ""]
            idx_words = [idx_word for idx_word in page.index if
                         idx_word[0].isdigit() is False and len(idx_word) > 2
                         and '_' not in idx_word]
            search_page_type = {
                'index_only': idx_words,
                'tags_only': tags_only,
                'index_and_tags': idx_words + tags_only}

            for idx in sorted(search_page_type[key]):
                word = idx.strip()
                timestamped_entry = chronology[timestamp].get(category)
                if timestamped_entry is None:
                    continue
                link = timestamped_entry[1]
                if word not in index:
                    index[word] = [link]
                else:
                    if link not in index[word]:
                        index[word].append(link)

    # Exclude links that feature in more than a certain percentage of entries:
    threshold = (len(all_pages) / 100) * ignore_threshold_percentage
    exclude_from_index = []
    for word, entries in index.items():
        if (len(entries) > threshold) and (word not in tags):
            exclude_from_index.append(word)
    for common_word in exclude_from_index:
        index.pop(common_word)
    print("Excluding the following common words from search index:\n{}"
          .format(", ".join(sorted(exclude_from_index))))
    words_used = [(idx, len(index[idx])) for idx in index]
    word_cloud = sorted(words_used, key=lambda x: x[1], reverse=True)

    return categories, tags, chronology, index, word_cloud


def add_to_chronology_dict(chronology, category, timestamp, value):
    if timestamp in chronology:
        for num in range(1, 3600):
            one_second_later = timestamp.replace(seconds =+ num)
            if one_second_later not in chronology:
                timestamp = one_second_later
                break
    if timestamp not in chronology:
        chronology[timestamp] = {}
    chronology[timestamp][category] = value

def generate_front_and_category_pages(site_title, homepage, searchpage,
                                      categories, tags, chronology, word_cloud,
                                      proj_root, css, ts_frmt,
                                      entries_to_show):
    generate_front_or_cat_page(site_title, homepage, searchpage, categories,
                               tags, chronology, word_cloud, proj_root, css,
                               ts_frmt, entries_to_show)

    for cat in categories:
        page_title = site_title + ' - ' + cat
        generate_front_or_cat_page(page_title, homepage, searchpage, [cat],
                                   tags, chronology, word_cloud, proj_root, css,
                                   ts_frmt, cat_page=True)



def generate_front_or_cat_page(site_title, homepage, searchpage, categories, tags,
                        chronology, word_cloud, proj_root, css, ts_frmt,
                        entries_to_show=10, cat_page=False):
    this_page = categories[0] + '/index.html' if cat_page else homepage
    with open(this_page, 'w') as op_file:
        print('<html>', file=op_file)
        print('    <header>', file=op_file)
        print('    <h3>{}</h3>'.format(site_title), file=op_file)
        print('        <nav>', file=op_file)
        print('<a href="{0}{1}">Home</a> | <a href="{0}{2}">Search</a>'
              .format(proj_root, homepage, searchpage), file=op_file)
        print('        </nav>', file=op_file)
        print('        <link rel="stylesheet" type="text/css" media="screen"' +
              ' href="{}" />'.format(css), file=op_file)
        print('        <title>{}</title>'.format(site_title), file=op_file)
        print('    </header>', file=op_file)
        print('    <body>', file=op_file)

        for cat in sorted(categories, reverse=True):
            show_more_link = True
            category = cat.lower()
            print('<h2>{}</h2>'.format(category), file=op_file)
            print('    <ul>', file=op_file)

            count = 0
            for timestamp, cat_dict in sorted(chronology.items(),
                                                   reverse=True):
                for _, (title, link) in cat_dict.items():
                    if category == link.split('/')[0]:
                        if (cat_page is True) or (count < int(entries_to_show)):
                            if cat_page is True:
                                link = link.split('/')[1]
                            print('<li><a href="{}">{}</a></li>'
                                  .format(link, title), file=op_file)
                        elif show_more_link:
                            show_more_link = False
                            print('<li><a href="{}/index.html">more...</a></li>'
                                  .format(category), file=op_file)
                        count += 1
            print('    </ul>', file=op_file)

        # TODO: Add some kind of javascript tag-cloud, word-cloud and category
        # list here.

        print('    </body>', file=op_file)
        print('</html>', file=op_file)

    print(this_page + ' generated.')


def generate_search_page(site_title, homepage, searchpage, index, css,
                         proj_root):
    with open(searchpage, 'w') as op_file:
        print('<html>', file=op_file)
        print('    <header>', file=op_file)
        print('    <h3>{}</h3>'.format(site_title), file=op_file)
        print('        <nav>', file=op_file)
        print('        <link rel="stylesheet" type="text/css" media="screen"' +
              ' href="{}" />'.format(css), file=op_file)
        print('        <title>Search</title>', file=op_file)
        print('<a href="{0}{1}">Home</a> | <a href="{0}{2}">Search</a>'
              .format(proj_root, homepage, searchpage), file=op_file)
        print('        </nav>', file=op_file)
        print('    </header>', file=op_file)
        print('    <body>', file=op_file)

        print('    <ul>', file=op_file)
        for word, links in sorted(index.items()):
            print('    <li><b><a name="{0}">{0}</a></b>'.format(word),
                  file=op_file)
            print('        <ul>', file=op_file)
            for link in links:
                print('        <li><a href="{0}">{0}</a></li>'.format(link),
                      file=op_file)
            print('        </ul>', file=op_file)
        print('    </ul>', file=op_file)

        print('    </body>', file=op_file)
        print('</html>', file=op_file)

        # TODO: Add some javascript wizardry so this displays a search box and
        # only presents the list of pages when that word is entered into the
        # box (everything else should be hidden).

    print(searchpage + ' generated.')


def generate_static_page(site_title, homepage, searchpage, meta, css, ts_frmt,
                         proj_root, media_dir="../media"):
    for cat in meta.categories:
        category = cat.lower()
        utils.mkdir(category)

        with open(os.path.join(category, meta.slug) + '.html', 'w') as op_file:
            print('<html>', file=op_file)
            print('    <title>{} ({})</title>'.format(
                  meta.title.title(), category.title()), file=op_file)
            print('    <body>', file=op_file)
            print('    <header>', file=op_file)
            print('    <h3>{} - {}</h3>'.format(
                  site_title.title(), category.title()), file=op_file)
            print('        <nav>', file=op_file)
            print('        <link rel="stylesheet" type="text/css"' +
                  ' media="screen" href="{}" />'.format(css), file=op_file)
            print('        <title>{}</title>'.format(meta.title), file=op_file)
            link_bar = '<a href="{0}{1}">Home</a> | '
            link_bar += '<a href="index.html">{3}</a> | '
            link_bar += '<a href="{0}{2}">Search</a>'
            print(link_bar.format(proj_root, homepage, searchpage,
                  category.title()), file=op_file)
            print('        </nav>', file=op_file)
            print('    </header>', file=op_file)
            print('    <article>', file=op_file)
            if meta.header_image != "":
                print('    <figure>', file=op_file)
                img_path = os.path.join(media_dir, meta.header_image)
                print('<img src="{}" />'.format(img_path), file=op_file)
                print('    </figure>', file=op_file)
            print('        <h2>{}</h2>'.format(meta.title), file=op_file)
            print(    meta.content, file=op_file)
            print('    </article></body>', file=op_file)
            print('<p></p>', file=op_file)
            date = \
                arrow.get(meta.date).format(ts_frmt) if meta.date != '' else ''

            print('        <h5>{}, {}</h5>'.format(meta.authors, date),
                  file=op_file)
            if meta.tags not in [[], ['']]:
                tags = []
                for tag in meta.tags:
                    linked_tag = '<a href="{proj_root}{search}#{tag}">{tag}</a>'
                    tags.append(linked_tag.format(proj_root=proj_root,
                                                  search=searchpage,
                                                  tag=tag.strip().lower()))
                print('    <tiny>Tags: {}</tiny>'.format(", ".join(tags)),
                      file=op_file)
                print('<p></p>', file=op_file)
            print('</html>', file=op_file)

def create_entry(folder, timestamp=None, title=None, filename=None,
                 categories='', name='', tags='', header_image='',
                 publish_bool='True', content=''):

    if type(categories) == list:
        categories = ", ".join([category.title() for category in categories])
    try:
        os.makedirs(folder)
    except:
        pass

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d")
    if title is None:
        title = \
            datetime.strptime(timestamp, "%Y-%m-%d").strftime("%A %d %B, %Y")
    if filename is None:
        filepath = os.path.join(folder, title + '.md')
    else:
        filepath = os.path.join(folder, filename + '.md')
    if os.path.exists(filepath):
        return filepath

    meta =  "Title:          {title}\n"
    meta += "Authors:        {name}\n"
    meta += "Date:           {date}\n"
    meta += "Tags:           {tags}\n"
    meta += "HeaderImage:    {header_image}\n"
    meta += "Category:       {categories}\n"
    meta += "Publish:        {publish_bool}\n"
    meta += "\n\n"
    meta = meta.format(title=title, name=name, date=timestamp, tags=tags,
                       header_image=header_image, categories=categories,
                       publish_bool=publish_bool)
    with open(filepath, 'w') as op:
        op.write(meta)
        op.write(content)
    return filepath

def edit(path_to_file):
    texteditor = utils.get_properties().get('text_editor', None)
    if texteditor is None:
        print("No texteditor set in properties file: {}\nRun '{} {}' manually"
              .format(utils.DEFAULT_PROPERTIES_FILE, texteditor, path_to_file))
    else:
        Popen([texteditor, path_to_file])

def new(categories):
    """Create a new entry"""
    output_directory = utils.get_properties().get('output_directory', '.')
    source_directory = utils.get_properties().get('source_directory', None)
    media_directory = utils.get_properties().get('media_directory', None)
    author = utils.get_properties().get('default_author', None)
    cats = "_".join([category.lower() for category in categories])
    filename = cats + '_' + datetime.now().strftime("%Y-%m-%d")
    path_to_file = create_entry(source_directory, filename=filename,
                                categories=categories, name=author)
    edit(path_to_file)

def make(categories):
    """Generate website"""
    # TODO: pass in category arg so only builds for one or more categories
    # TODO: Include the ability to selectively publish or exclude certain
    # categories, i.e. ./scripts/generate_website.py --only=Blog
    # or ./scripts/generate_website.py --exclude=Work, Personal
    if categories:
        raise NotImplementedError(
            "Generating only selected categories is not implemented yet!")
    time_now = arrow.now().strftime('%d-%b-%y %H:%M:%S')
    print("{}: Generating pages".format(time_now))
    properties = utils.get_properties()
    generate_pages(properties=properties)

def view():
    """Open locally generated html in browser"""
    browser = utils.get_properties().get('default_browser', None)
    output_directory = utils.get_properties().get('output_directory', None)
    Popen([browser, output_directory + "index.html"])

def properties():
    """View properties"""
    # TODO: replace this with get and set
    print("Contents of {}:".format(utils.DEFAULT_PROPERTIES_FILE))
    pprint(utils.get_properties())

def collect_args():
    parser = argparse.ArgumentParser(
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(title='commands')

    new_cmd = subparsers.add_parser('new', help=new.__doc__)
    new_cmd.add_argument(
        'categories', nargs='*',
        help='list of categories under which to file this entry')
    new_cmd.set_defaults(command=new)

    make_cmd = subparsers.add_parser('make', help=make.__doc__)
    make_cmd.add_argument('categories', nargs='*',
                          help='Selected list of categories to build')
    make_cmd.set_defaults(command=make)

    view_cmd = subparsers.add_parser('view', help=view.__doc__)
    view_cmd.set_defaults(command=view)

    prop_cmd = subparsers.add_parser('properties', help=properties.__doc__)
    prop_cmd.set_defaults(command=properties)

    return parser

def main():
    command, args = utils.parse_args(collect_args())
    command(**args)

if __name__ == "__main__":
    sys.exit(main())

import csv
import logging
from datetime import datetime
from scrapy.spiders import CrawlSpider
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s', )

file_handler = logging.FileHandler('gd_blog_parser.log')
logging.getLogger().addHandler(file_handler)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
file_handler.setFormatter(formatter)


class GDBlogCrawler(CrawlSpider):
    """This spider is used when no data exists"""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        logging.getLogger('scrapy').setLevel(logging.WARNING)

    name = 'blog_scraper'
    allowed_domains = ['blog.griddynamics.com']
    start_urls = [
        'https://blog.griddynamics.com/all-authors/'
    ]
    output_articles = 'articles.csv'
    output_authors = 'authors.csv'
    first_row_articles = True  # to write column headers in csv only once
    first_row_authors = True  # same as above
    author_counter = 1  # for console output of parsing process, e.g. 'parsing [1/2] articles'
    authors_len = None  # same as above
    articles_len = 0  # same as above

    def parse_author(self, response):
        """Function to parse each author and extract data to .csv file"""
        logging.info('Parsing author page [{current}/{all}] -> {url}'.format(current=self.author_counter,
                                                                             all=self.authors_len,
                                                                             url=response.url))
        self.author_counter += 1
        author_info = response.css('div.modalbg')
        for field in author_info:
            full_name = field.css('div.authorcard.popup > div.row > div.titlewrp > h3::text').get()
            job_title = field.css('div.authorcard.popup > div.row > div.titlewrp > p.jobtitle::text').get()
            author_articles = field.css('div.authorcard.popup > div.postsrow > div.row > a::attr(href)').getall()
            articles_counter = len(author_articles)
            raw_urls = field.css('div.authorcard.popup > div.row > div.imgwrp > ul.socicons.mb15')
            all_urls = raw_urls.css('a::attr(href)').getall()
            linkedin = []
            contacts = []
            for url in all_urls:
                if 'linkedin' in url:
                    linkedin = url
                else:
                    contacts.append(url)
            with open(self.output_authors, mode='a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if self.first_row_authors:
                    writer.writerow(['full_name', 'job_title', 'linkedin', 'contact', 'articles_counter'])
                    self.first_row_authors = False
                if len(contacts) is not 0:
                    for contact in contacts:
                        if len(linkedin) is 0:
                            writer.writerow([full_name, job_title, '', contact, articles_counter])
                            # if cell is empty default value is NaN. replacing NaN with empty symbol here and below
                        else:
                            writer.writerow([full_name, job_title, linkedin, contact, articles_counter])
                else:
                    if len(linkedin) is 0:
                        writer.writerow([full_name, job_title, '', '', articles_counter])
                    else:
                        writer.writerow([full_name, job_title, linkedin, '', articles_counter])

            for article_url in author_articles:
                yield response.follow(article_url, self.parse_article)  # parsing each article

    def parse_article(self, response, write_to_csv=True):
        """Function to parse each article and extract data to .csv file"""
        self.articles_len += 1
        logging.info('Parsing article page -> {url}'.format(url=response.url))
        search_results = response.css('div#woe')
        for article in search_results:
            title = str(article.css('div.container > div#wrap > h2.mb30::text').get())\
                .replace('\r', '').replace('\n', ' ')
            url = response.url
            text_raw_with_tags = article.css('section.postbody > div.container > p').getall()
            text = ''
            for row in text_raw_with_tags:
                soup_raw = BeautifulSoup(row, features='lxml')
                text += soup_raw.get_text().strip()  # getting rid of html tags
                if len(text) > 160:
                    text = text[:161].replace('\r', '').replace('\n', ' ')
            publication_date_as_str = article.css('div.authwrp > div.sdate::text').get()[9:21]
            publication_date = datetime.strptime(publication_date_as_str, '%b %d, %Y').date()
            authors_raw = article.css('div.authwrp > div.author.authors > div.sauthor '
                                      '> span > a.goauthor > span.name::text').getall()
            authors = []
            for author in authors_raw:
                authors.append(author.strip())
            tags = response.css('div.post-tags > a.tag-link::text').getall()
            if write_to_csv:
                with open(self.output_articles, mode='a', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    if self.first_row_articles:
                        writer.writerow(['title', 'url', 'text', 'publication_date', 'author', 'tag'])
                        self.first_row_articles = False
                    if len(tags) > len(authors):
                        for tag in tags:
                            for author in authors:
                                writer.writerow([title, url, text, publication_date, author, tag])
                    else:
                        for author in authors:
                            for tag in tags:
                                writer.writerow([title, url, text, publication_date, author, tag])
            else:
                return title, url, text, publication_date, authors, tags

    def parse(self, response):
        """Function to parse /all-authors/ page and get url to each author page"""
        logging.info('Getting urls to authors pages -> {url}'.format(url=response.url))
        authors_list = response.css('div.postsrow > div.row.viewmore > a.viewauthor::attr(href)').getall()
        logging.info('Urls collected. Starting iteration process . . .')
        counter = 0
        for author in authors_list:
            #author_url = author.css('a.authormore::attr(href)').get()
            counter += 1
            yield response.follow(author, self.parse_author)
        lost_authors = ('/author/ezra/',
                        '/author/anton/',
                        '/author/pavel-vasilyev/')
        # these authors exists, but they are not displayed at /all-authors/ page
        for url in lost_authors:
            counter += 1
            yield response.follow(url, self.parse_author)
        self.authors_len = counter

    def close(self, reason):
        """Function to explicitly close spider"""
        logging.info('Spider closed. '
                     '{authors_len} Author(s) extracted to {authors_file}, '
                     '{articles_len} Article(s) extracted to {articles_file}.'
                     .format(authors_len=self.authors_len,
                             authors_file=self.output_authors,
                             articles_len=self.articles_len,
                             articles_file=self.output_articles))

from distutils.core import setup
from setuptools import find_packages

version = '0.1'
setup(
    name='ScrapyElasticSearch2',
    version=version,
    license='Apache License, Version 2.0',
    description='Scrapy pipeline which allow you to store multiple scrapy items in Elastic Search.',
    author='Michael Malocha',
    author_email='michael@knockrentals',
    url='https://github.com/knockrentals/scrapy-elasticsearch2',
    packages = find_packages(),
    download_url = (
        'https://github.com/knockrentals/scrapy-elasticsearch2/tarball/master'
    ),
    keywords=['scrapy', 'elastic search', 'elasticsearch', 'scrapy'],
    py_modules=['scrapyelasticsearch2'],
    platforms = ['Any'],
    install_requires = ['scrapy', 'pyes'],
    classifiers = [ 'Development Status :: 4 - Beta',
                    'Environment :: No Input/Output (Daemon)',
                    'License :: OSI Approved :: Apache Software License',
                    'Operating System :: OS Independent',
                    'Programming Language :: Python'],
)

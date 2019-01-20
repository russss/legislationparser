from setuptools import setup
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open('README.md') as f:
    long_description = f.read()

setup(name='legislationparser',
      version='0.1',
      description='UK Legislation XML Parser',
      long_description=long_description,
      long_description_content_type='text/markdown',
      license='MIT',
      author='Russ Garrett',
      author_email='russ@garrett.co.uk',
      url='https://github.com/russss/legislationparser',
      classifiers=[
          'Development Status :: 4 - Beta',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
      ],
      keywords='legislation parliament uk',
      python_requires='>=3.6',
      packages=['legislationparser'],
      install_requires=['lxml', 'yattag']
      )

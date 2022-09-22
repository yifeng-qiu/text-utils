"""
Extract line items from account statements of Bank of America into CSV file.
Author: Yifeng Qiu
Last Updated: 2022-09-22
"""
import PyPDF2
import os
import re
import csv
from typing import List
from os import DirEntry

DATE_PATTERN = r'[0-9]{2}/[0-9]{2}/[0-9]{2}'
DOLLAR_AMOUNT_PATTERN = r'[+-]?[0-9]{1,3}(?:,?[0-9]{3})*\.[0-9]{2}'


def seekto(lines: List[str], target, startline: int = 0) -> int:
    """
    Find the first occurrence of the target content and return its line number
    :param lines: the content where the target will be searched
    :param target: regex pattern for the target
    :param startline: the line from which the search will be performed
    :return: line number of the target, if not found, return -1
    """
    for i in range(startline, len(lines)):
        if len(re.findall(target, lines[i])) == 1:
            return i
    return -1


def extract_info(content: List[str], end_target: str, startline: int = 1) -> (List[str], int):
    """

    :param content: the content from which the information will be extracted
    :param end_target: a text indicating the end of the table content
    :param startline: the line number from which the extraction should be performed
    :return: the extracted content, the line number of the end_target
    """

    j = startline
    result = []
    while j < len(content) and re.search(end_target, content[j]) is None:
        match = re.match(DATE_PATTERN, content[j])
        if match:
            date = match.group()
            matched_date_span = match.span()
            desc_start_pos = matched_date_span[1] + 1
        else:
            j += 1
            continue  # skip lines until a date is found

        # extract dollar amount
        description = ''
        while j < len(content):
            match = re.search(DOLLAR_AMOUNT_PATTERN, content[j])
            if match is not None:
                matched_amount_span = match.span()
                desc_end_pos = matched_amount_span[0]  # non inclusive
                value = match.group()
                description += content[j][desc_start_pos:desc_end_pos]
                break
            else:
                # the record may span multiple lines, we need to continue read lines until the dollar amount
                # is found and then we need to concatenate all the descriptions.
                description += content[j][desc_start_pos:]
                desc_start_pos = 0
                j += 1
        result.append([date, description, value])
        j += 1

    if j == len(content):
        j = -1
    return result, j


def get_checking_account_pages(content: str) -> tuple:
    """

    :param content: the content to be searched
    :return: tuple of the first page and the last page
    """
    checking_account_first_page = 3
    checking_account_last_page = 3
    # this is statement for both checking and savings accounts
    match = re.search('BofA Core Checking [^\r\n]+ Page ([0-9])', content)
    if match:
        checking_account_first_page = int(match.group(1))
    match = re.search('Regular Savings [^\r\n]+ Page ([0-9])', content)
    if match:
        checking_account_last_page = int(match.group(1)) - 1
    return checking_account_first_page, checking_account_last_page


def process_pdf_file(pdf_file: DirEntry, csv_writer) -> None:
    """

    :param pdf_file: DirEntry object representing the PDF file being processed
    :param csv_writer: csv writer object
    :return: None
    """
    filename = os.path.splitext(pdf_file.name)[0]
    with open(pdf_file.path, 'rb') as pdf_fp:
        pdf_obj = PyPDF2.PdfReader(pdf_fp)
        page1 = pdf_obj.getPage(0)
        content = page1.extract_text()
        if content.find('Your combined statement') >= 0:
            checking_account_pages = get_checking_account_pages(content)
            # account summary is on page 3
            account_summary = pdf_obj.getPage(2).extract_text().splitlines()
        else:
            # account summary is on page 1
            checking_account_pages = [3, pdf_obj.getNumPages()]
            account_summary = pdf_obj.getPage(0).extract_text().splitlines()

        sections = ['Deposits and other additions',
                    'Withdrawals and other subtractions',
                    'Checks',
                    'Service fees']
        section_values = ['0.00', '-0.00', '-0.00', '-0.00']
        section_idx = 0

        for line in account_summary:
            if section_idx == len(sections):
                break
            match = re.search(sections[section_idx] + ' (' + DOLLAR_AMOUNT_PATTERN + ')',
                              line)
            if match:
                value = match.group(1)
                section_values[section_idx] = value
                section_idx += 1

        # Extract all the pages for the checking account and concatenate the lines
        # Here we can potentially use a generator instead of getting all the content at once
        content = []
        for p in range(checking_account_pages[0], checking_account_pages[1] + 1):
            content.extend(pdf_obj.getPage(p - 1).extract_text().splitlines())

        i = 0
        for idx, section in enumerate(sections):
            if section_values[idx] not in ['0.00', '-0.00']: # only process this section if its value is non-zero
                try:
                    i = process_statement_section(content, section, csv_writer, filename, i)
                except ValueError as err:
                    raise err


def process_statement_section(content: List[str], section_label: str, csv_writer, filename: str, startline: int) -> int:
    """

    :param content: the content to extract information from
    :param section_label: the label of the section to be processed
    :param csv_writer: csv_writer object
    :param filename: the filename
    :param startline: the line number from which the extraction should be performed
    :return: the last line where the extraction stopped
    """
    section_begin_label_pattern = '(' + section_label + '$)'
    section_end_label_pattern = 'Total ' + section_label.lower()
    i = seekto(content, section_begin_label_pattern, startline)
    if i != -1:
        i += 2  # Skipping the header of the statement table
        # now we are at the start of the table for the deposits
        result, i = extract_info(content, section_end_label_pattern, i)
        if i == -1:
            raise ValueError(f'Something went wrong with extracting {section_label}')
        else:
            if csv_writer:
                for row in result:
                    csv_writer.writerow(row + [filename])
    return i


if __name__ == '__main__':
    statementFolder = os.environ['STATEMENT_FOLDER']  # for obvious security reason
    with open('statement.csv', 'a', newline='', encoding='utf-8') as csv_fp:
        csvWriter = csv.writer(csv_fp)
        dirIterator = os.scandir(statementFolder)
        for file in dirIterator:
            if file.is_file() and file.name.endswith('pdf'):
                try:
                    process_pdf_file(file, csvWriter)
                    print(f'Extraction of {file.name} completed successfully.')
                except ValueError as e:
                    print(f'Error processing file {file.name}, skipped')
                    print(f'The error message was {e.args[0]}')

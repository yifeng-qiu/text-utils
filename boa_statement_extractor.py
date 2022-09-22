import PyPDF2
import os
import re
import csv
from typing import Dict, List
from os import DirEntry

# file = r'U:\PrivateData\BankAccount\BOA\Checking 2651\eStmt_2016-12-15.pdf'


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
    date_pattern = r'[0-9]{2}/[0-9]{2}/[0-9]{2}'
    dollar_amount_pattern = r'[+-]?[0-9]{1,3}(?:,?[0-9]{3})*\.[0-9]{2}'
    j = startline
    result = []
    while j < len(content) and re.search(end_target, content[j]) is None:
        result = re.match(date_pattern, content[j])
        if result:
            date = result[0]
            matched_date_span = result.span()
            desc_start_pos = matched_date_span[1] + 1
        else:
            raise ValueError('Error while extracting date.')

        # extract dollar amount
        result = re.search(dollar_amount_pattern, content[j])
        if result is not None:
            matched_amount_span = result.span()
            desc_end_pos = matched_amount_span[0]  # non inclusive
            value = result.group()
            description = content[j][desc_start_pos:desc_end_pos]
        else:
            # the amount is on the next line, we need to append the remainder of the description
            # on the next line, if any, to the portion from the current line
            description = content[j][desc_start_pos:]
            j += 1
            result = re.search(dollar_amount_pattern, content[j])
            if result is not None:
                value = result.group()
                matched_amount_span = result.span()
                description += ' ' + content[j][
                                     :matched_amount_span[0]]  # insert a white space between the two portions
            else:
                raise ValueError('Error while extracting dollar amount.')

        result.append([date, description, value])

    if j == len(content):
        j = -1
    return result, j


def get_checking_account_pages(content: str) -> tuple:
    """

    :param content: the content to be searched
    :return: tuple of the first page and the last page
    """
    checking_account_first_page = 3  # the default page where the statement begins
    checking_account_last_page = 4  # the default page where the statement ends
    if content.find('Your combined statement') >= 0:
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

        checking_account_pages = get_checking_account_pages(content)

        # we extract all the pages for the checking account and concatenate the lines
        content = []
        for p in range(checking_account_pages[0], checking_account_pages[1] + 1):
            content.extend(pdf_obj.getPage(p - 1).extract_text().splitlines())

        i = seekto(content, '(Deposits and other additions$)', 0)
        if i != -1:
            i += 2  # Skipping the header of the statement table
        else:
            raise ValueError('Format error, no valid information found')

        # now we are at the start of the table for the deposits
        result1, i = extract_info(content, 'Total deposits and other additions', i)
        if i == -1:
            raise ValueError('Something went wrong')

        i = seekto(content, '(Withdrawals and other subtractions$)', i)
        if i != -1:
            i += 2  # Skipping the header of the statement table
        else:
            raise ValueError('Format error, no valid information found')

        result2, i = extract_info(content, 'Total withdrawals and other subtractions', i)
        if i == -1:
            raise ValueError('Something went wrong')
        else:
            result = result1 + result2
            for row in result:
                csv_writer.writerow(row + [filename])
            print('Extraction completed successfully.')


if __name__ == '__main__':
    # statementFolder = r'U:\PrivateData\BankAccount\BOA\Checking 2651'
    statementFolder = os.environ['STATEMENT_FOLDER']
    with open('test.csv', 'a', newline='', encoding='utf-8') as csv_fp:
        csvWriter = csv.writer(csv_fp)
        dirIterator = os.scandir(statementFolder)
        for file in dirIterator:
            if file.is_file() and file.name.endswith('pdf'):
                try:
                    process_pdf_file(file, csvWriter)
                except ValueError:
                    print(f'Error processing file {file.name}, skipped')

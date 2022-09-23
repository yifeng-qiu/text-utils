# Save a backup of RedFin listing including the information page and high-resolution photos
# Author:   Yifeng Qiu
# Date:     2020-08-28


import re, requests, os
from bs4 import BeautifulSoup
import pdfkit

main_folder = r'D:\Temporary Storage\House Hunting'
# Request web page
house_url = r'https://www.redfin.com/CA/San-Francisco/300-Cresta-Vista-Dr-94127/home/1694276'
headers = {'User-Agent': r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.74 Safari/537.36 Edg/79.0.309.43"}
web_content = requests.get(house_url, headers=headers).content.decode()
soup = BeautifulSoup(web_content, 'lxml')

# Extract information from title
title = soup.find('title').text
title_info = title.split(sep='|')
title_info = [s.lstrip().rstrip() for s in title_info]
address = title_info[0]
MLS_ID = title_info[1][5:]

# Create Folders
target_folder = os.path.join(main_folder, address)
if not os.path.exists(target_folder):
    os.makedirs(target_folder)

img_folder = os.path.join(target_folder, 'Images')
if not os.path.exists(img_folder):
    os.makedirs(img_folder)

# Print main page into PDF
pdf_filename = '_'.join(title_info) + '.pdf'
pdfkit.from_url(house_url, os.path.join(target_folder, pdf_filename))

# Extract all images names
img_re = re.compile(MLS_ID + r'[_0-9a-zA-Z]+\.jpg')
all_images = img_re.findall(web_content)
all_images = list(set(all_images))
image_count = len(all_images)

# Extract path to high-res photos
img_path_re = re.compile(r'https://ssl.cdn-redfin.com/photo/[0-9]/bigphoto/[0-9]+/')
img_path_match = img_path_re.finditer(web_content)
img_path = next(img_path_match).group(0)

# Download all high-resolution images
for idx, img in enumerate(all_images):
    print('Downloading image {} of {}'.format(idx + 1, image_count))
    url = img_path + img
    myfile = requests.get(url)
    with open(os.path.join(img_folder, img), 'wb') as fp:
        fp.write(myfile.content)

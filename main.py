
import argparse
import time
from loguru import logger
from utils import parse_pdf, save_pdf_data


def parse_args():
    parser = argparse.ArgumentParser(description='PDF解析工具')
    parser.add_argument('--pdf_path', type=str, required=True, help='输入PDF文件路径')
    parser.add_argument('--out_path', type=str, default='test.txt', help='输出文件路径')
    return parser.parse_args()


def process_pdf(pdf_path, out_path):
    start_time = time.time()

    all_pdf_pages = parse_pdf(pdf_path)
    page_lst = all_pdf_pages.pdf_pages
    end_time = time.time()
    logger.info(f'页数：{len(page_lst)}， 解析耗时：{round(end_time - start_time, 2)}s')

    save_pdf_data(page_lst, out_path)
    logger.info(f'输出文件：{out_path}')


if __name__ == '__main__':
    args = parse_args()
    process_pdf(args.pdf_path, args.out_path)


from typing import List, Dict, Optional

from utils.utils_split_text import simple_split_text_list, Document
from utils.utils_pymupdf_parse import parse_pdf, PdfPage, ElementType
from utils.tools import split_datas
from utils.env import TABLE_FORMAT, CHUNK_SIZE_LIST, CHUNK_OVERLAP_LIST, DOC_SUM_NUM

from functools import partial
from collections import defaultdict


def list_to_markdown(datas: List[List[str]]) -> str:
    if not datas:
        return ''
    # 获取列名和数据
    headers = datas[0]
    data = datas[1:]

    # 构建Markdown表格字符串
    markdown_table = "| " + " | ".join(str(head) if head else '' for head in headers) + " |\n"
    markdown_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"

    for row in data:
        markdown_table += "| " + " | ".join(str(cell) if cell else '' for cell in row) + " |\n"

    return markdown_table


def list_to_html(datas: List[List[str]]) -> str:
    if not datas:
        return ''
    # 构建HTML表格字符串
    html_table = "<table>\n"

    # 添加表头
    html_table += "<tr>"
    for column in datas[0]:
        column = column if column else ''
        html_table += f"<th>{column}</th>"
    html_table += "</tr>\n"

    # 添加数据行
    for row in datas[1:]:
        html_table += "<tr>"
        for cell in row:
            cell = cell if cell else ''
            html_table += f"<td>{cell}</td>"
        html_table += "</tr>\n"

    html_table += "</table>"
    return html_table


def format_table_lst(table_lst: List[List[str]], format_type=TABLE_FORMAT) -> str:
    """
    将table_lst格式化为字符串

    :param table_lst:
    :param format_type:
    :return:
    """
    table_str = ''
    if format_type == 'markdown':
        table_str = list_to_markdown(table_lst)
    elif format_type == 'html':
        table_str = list_to_html(table_lst)

    return table_str


def length_function(text: str, table_map: Dict[str, str]) -> int:
    """
    检测'@{page_number}_{element_no}@'是否存在，若存在，先替换为table_lst，再计算长度
    :param text:
    :param table_map:
    :return:
    """

    for table_id, table_str in table_map.items():
        if table_id in text:
            text = text.replace(table_id, table_str)

    return len(text)


def split_pdf_page_lst(page_lst: List[PdfPage],
                       chunk_size: int = 4000,
                       chunk_overlap: int = 200,
                       format_type='markdown',
                       sum_num: int = 100,
                       separators: Optional[List[str]] = None,
                       ) -> List[Document]:
    table_map: Dict[str, str] = dict()
    texts = []
    metadatas = []
    block_index = defaultdict(list)

    res_lst = split_datas(page_lst, sum_num)
    for i, res in enumerate(res_lst):
        res_texts = []
        for one_page in res:
            page_number = one_page.page_number
            page_elements = one_page.page_elements
            page_text_lst = []
            for one_element in page_elements:
                element_type = one_element.element_type
                if element_type == ElementType.text:
                    text = one_element.element_value
                    page_text_lst.append(text)

                elif element_type == ElementType.table:
                    element_no = one_element.element_no
                    table_id = f'@page_{page_number}_element_{element_no}_table@'

                    table_map[table_id] = format_table_lst(one_element.element_value, format_type=format_type)
                    page_text_lst.append(table_id)

                elif element_type == ElementType.image:
                    element_no = one_element.element_no
                    table_id = f'@page_{page_number}_element_{element_no}_image@'

                    table_map[table_id] = one_element.element_value
                    page_text_lst.append(table_id)
            res_texts.append(''.join(page_text_lst))
            block_index[i].append({
                'page_number': page_number,
                'start_index': len(''.join(res_texts[:-1])),
                'end_index': len(''.join(res_texts))
            })
        texts.append(''.join(res_texts))
        metadatas.append({
            'block_number': i
        })

    length_function_new = partial(length_function, table_map=table_map)

    split_docs = simple_split_text_list(texts, metadatas,
                                        chunk_size=chunk_size,
                                        chunk_overlap=chunk_overlap,
                                        add_start_index=True,
                                        length_function=length_function_new,
                                        separators=separators)

    # 将split_docs中的table_id替换为table_str
    for doc in split_docs:
        page_text = doc.page_content
        table_id_lst = []
        for table_id, table_str in table_map.items():
            if table_id in page_text:
                page_text = page_text.replace(table_id, table_str)
                table_id_lst.append(table_id)

        for table_id in table_id_lst:
            table_map.pop(table_id)
        doc.page_content = page_text

        block_number = doc.metadata['block_number']
        start_index = doc.metadata['start_index']
        block_index_lst = block_index[block_number]
        for one_block_index in block_index_lst:
            if one_block_index['start_index'] <= start_index < one_block_index['end_index']:
                doc.metadata['page_number'] = one_block_index['page_number']
                doc.metadata['start_index'] = start_index - one_block_index['start_index']
                doc.metadata.pop('block_number')
                break

    return split_docs


def parse_and_split_pdf(pdf_path: str,
                        chunk_size: int = 4000,
                        chunk_overlap: int = 200,
                        format_type='markdown',
                        sum_num: int = 100,
                        separators: Optional[List[str]] = None,
                        ) -> List[Document]:
    """
    切割pdf，返回切割后的文档列表

    :param pdf_path:
    :param chunk_size:
    :param chunk_overlap:
    :param format_type:
    :param sum_num:
    :param separators:
    :param split_type: 切割规则，默认按照原系统切割，1：自定义；2：fastgpt切割规则
    :return:
    """
    all_pdf_pages = parse_pdf(pdf_path)
    page_lst = all_pdf_pages.pdf_pages
    split_docs = split_pdf_page_lst(page_lst,
                                    chunk_size=chunk_size,
                                    chunk_overlap=chunk_overlap,
                                    format_type=format_type,
                                    sum_num=sum_num,
                                    separators=separators,
                                    )

    return split_docs


def parse_pdf_chunk(file_path: str, ud_chunk_size: int = None, separators: Optional[List[str]] = None, split_type: int = None) -> List[Document]:
    """
    解析pdf
    :param file_path:
    :param ud_chunk_size: 用户自定义的切割长度
    :param separators: 用户自定义的切割符号
    :param split_type: 切割规则，默认按照原系统切割，1：自定义；2：fastgpt切割规则
    :return:
    """
    all_split_docs = []
    if not ud_chunk_size:
        for chunk_size, chunk_overlap in zip(CHUNK_SIZE_LIST, CHUNK_OVERLAP_LIST):
            split_docs = parse_and_split_pdf(file_path,
                                             chunk_size=chunk_size,
                                             chunk_overlap=chunk_overlap,
                                             format_type=TABLE_FORMAT,
                                             sum_num=DOC_SUM_NUM,
                                             separators=separators,
                                             split_type=split_type,
                                             )
            all_split_docs.extend(split_docs)
    else:
        all_split_docs = parse_and_split_pdf(file_path,
                                             chunk_size=ud_chunk_size,
                                             chunk_overlap=ud_chunk_size // 5,
                                             format_type=TABLE_FORMAT,
                                             sum_num=DOC_SUM_NUM,
                                             separators=separators,
                                             split_type=split_type,
                                             )

    return all_split_docs


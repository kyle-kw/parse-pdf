
import re
import fitz
from enum import Enum
from typing import Union, List, Tuple
from pydantic import BaseModel, Field
from pathlib import Path

class ElementType(str, Enum):
    text = 'text'
    image = 'image'
    table = 'table'


class PdfElement(BaseModel):
    element_no: int = Field(description='元素编号')
    element_type: ElementType = Field(description='元素类型')
    element_bbox: Tuple[float, ...] = Field(description='元素坐标')
    element_value: Union[str, bytes, list] = Field(description='元素内容')


class PdfPage(BaseModel):
    page_number: int = Field(description='页码')
    page_height: float = Field(description='页高')
    page_width: float = Field(description='页宽')
    page_elements: List[PdfElement] = Field(description='页元素')


class AllPdfPage(BaseModel):
    pdf_name: str = Field(description='pdf名称')
    pdf_pages: List[PdfPage] = Field(description='pdf页列表')


def bbox_include(bbox1, bbox2):
    """
    判断bbox1是否包含bbox2
    :param bbox1:
    :param bbox2:
    :return:
    """
    x0, y0, z0, w0 = bbox1
    x1, y1, z1, w1 = bbox2
    if x0 <= x1 and y0 <= y1 and z0 >= z1 and w0 >= w1:
        return True
    else:
        return False


def parse_block_content(block) -> dict:
    """
    解析块的内容
    :param block:
    :return:
    """
    if block['type'] == 0:
        block_text = ''
        for line in block['lines']:
            for span in line['spans']:
                block_text += span['text']
            block_text += '\n'
        block_text += '\n'

        return {
            'bbox': block['bbox'],
            'text': block_text,
            'block_no': block['number'],
            'block_type': block['type'],
        }
    elif block['type'] == 1:
        return {
            'bbox': block['bbox'],
            'text': block['image'],
            'block_no': block['number'],
            'block_type': block['type'],
        }


def deal_table_nest(table_lst):
    # 处理表格嵌套的问题
    for i, table1 in enumerate(table_lst):
        one_bbox = table1['bbox']
        one_text = table1['text']
        for j, table2 in enumerate(table_lst):
            if i == j:
                continue
            two_bbox = table2['bbox']
            two_text = table2['text']
            if bbox_include(one_bbox, two_bbox):
                re_rep = re.compile(
                    re.escape(' '.join([d for d in two_text[0] if d is not None]).strip()) +
                    '.*?' +
                    re.escape(' '.join([d for d in two_text[-1] if d is not None]).strip()),
                    re.S
                )
                for w, col in enumerate(one_text):
                    for z, row in enumerate(col):
                        if not row:
                            continue
                        row_lst = re_rep.findall(row)
                        if row_lst:
                            table1['text'][w][z] = re_rep.sub('', row)

                if table1['is_nest'] == 2:
                    temp_tables = list(filter(lambda x: table1['table_no'] in x['text_dict'], table_lst))
                    if not temp_tables:
                        continue

                    temp_table = temp_tables[0]
                    temp_table['text_dict'][table2['table_no']] = (two_bbox, table2['text'])
                    temp_table['text_dict'][table1['table_no']] = (one_bbox, table1['text'])
                    table2['is_nest'] = 2
                else:
                    table1['text_dict'][table1['table_no']] = (one_bbox, table1['text'])
                    table1['text_dict'][table2['table_no']] = (two_bbox, table2['text'])
                    table1['is_nest'] = 1
                    table2['is_nest'] = 2

    # 筛序掉嵌套的表格
    table_lst = list(filter(lambda x: x['is_nest'] != 2, table_lst))

    return table_lst


def deal_block_include_table(block_lst, table_lst):
    # 处理block_lst包含的表格
    element_lst = []
    for block in block_lst:
        for table in table_lst:
            if block['block_type'] == 0 and bbox_include(table['bbox'], block['bbox']):
                if table['table_no'] not in element_lst:
                    element_lst.append(table['table_no'])
                break
        else:
            element_lst.append({
                'bbox': block['bbox'],
                'text': block['text'],
                'element_no': block['block_no'],
                'element_type': block['block_type'],
            })

    return element_lst


def format_element_lst(element_lst, table_lst) -> List[PdfElement]:
    # 格式化element_lst
    element_list_res = []
    t = 1
    table_map = {d['table_no']: d for d in table_lst}
    for element in element_lst:
        if isinstance(element, int):
            table_element = table_map[element]
            if table_element['is_nest'] == 0:
                element_list_res.append(PdfElement(element_no=t,
                                                   element_type=ElementType.table,
                                                   element_bbox=table_element['bbox'],
                                                   element_value=table_element['text']))
            elif table_element['is_nest'] == 1:
                for _, table_element_temp in table_element['text_dict'].items():
                    element_list_res.append(PdfElement(element_no=t,
                                                       element_type=ElementType.table,
                                                       element_bbox=table_element_temp[0],
                                                       element_value=table_element_temp[1]))
                    t += 1
        elif isinstance(element['text'], str):
            element_list_res.append(PdfElement(element_no=t,
                                               element_type=ElementType.text,
                                               element_bbox=element['bbox'],
                                               element_value=element['text']))
        elif isinstance(element['text'], bytes):
            # 处理图片
            try:
                element_list_res.append(PdfElement(element_no=t,
                                                   element_type=ElementType.image,
                                                   element_bbox=element['bbox'],
                                                   element_value=element['text']))
            except:
                pass

        t += 1

    return element_list_res


def parse_pdf(path: Union[str, Path]) -> AllPdfPage:
    """
    解析pdf
    :param path:
    :return:
    """
    page_lst = []
    with fitz.open(path) as pdf:
        for num_page, page in enumerate(pdf):
            blocks = page.get_text("dict").get('blocks')
            block_lst = []
            for block in blocks:
                block_lst.append(parse_block_content(block))

            tabs = page.find_tables()
            table_lst = []
            for i, tab in enumerate(tabs):
                bbox = tab.bbox
                tab_value = tab.extract()
                table_lst.append({
                    'bbox': bbox,
                    'text': tab_value,
                    'block_lst': [],
                    'table_no': i,
                    'is_nest': 0,
                    'text_dict': dict()
                })

            # 处理表格嵌套的问题
            table_lst = deal_table_nest(table_lst)

            # 处理block_lst包含的表格
            element_lst = deal_block_include_table(block_lst, table_lst)

            # 格式化element_lst
            element_list_res = format_element_lst(element_lst, table_lst)

            _, _, width, height = page.bound()
            page_model = PdfPage(page_number=num_page + 1,
                                 page_height=height,
                                 page_width=width,
                                 page_elements=element_list_res)
            page_lst.append(page_model)

    pdf_name = ''
    if isinstance(path, str):
        pdf_name = Path(path).name
    elif isinstance(path, Path):
        pdf_name = path.name

    all_pdf_pages = AllPdfPage(pdf_name=pdf_name,
                               pdf_pages=page_lst)
    return all_pdf_pages


def save_pdf_data(page_lst: List[PdfPage], path: Union[str, Path] = 'test.txt') -> None:
    """
    将解析结果保存成txt文件
    :param page_lst:
    :param path:
    :return:
    """
    with open(path, 'w') as f:
        for page in page_lst:
            page_number = page.page_number
            page_elements = page.page_elements
            f.write(f'page_number: {page_number}\n')
            for page_element in page_elements:
                if page_element.element_type == ElementType.text:
                    f.write(page_element.element_value)
                elif page_element.element_type == ElementType.image:
                    f.write('========= image ===========')
                    f.write('\n')
                elif page_element.element_type == ElementType.table:
                    # page_element.element_value列表为一个二维列表，转换为md的表格格式
                    table_lst = page_element.element_value
                    table_fa = [i if i else '' for i in table_lst[0]]
                    table_header = '|'.join(['-' * 10] * len(table_fa)) + '\n'
                    f.write(table_header)
                    # 表头内容
                    table_header_content = '|'.join(table_fa) + '\n'
                    f.write(table_header_content)
                    f.write(table_header)
                    # 表格内容
                    for table_content in table_lst[1:]:
                        table_content = [i if i else '' for i in table_content]
                        table_content = '|'.join(table_content) + '\n'
                        f.write(table_content)


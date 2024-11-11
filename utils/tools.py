
import math
import copy


def split_datas(datas, batch=500):
    # 将数据切割
    batch_num = math.ceil(len(datas) / batch)
    action_list = []
    for num in range(batch_num):
        # 将数据每 batch 条切割
        data_model = copy.deepcopy(datas[num * batch: (num + 1) * batch])
        action_list.append(data_model)

    return action_list

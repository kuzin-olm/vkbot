# -*- coding: utf-8 -*-
import pandas as pd

pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_rows', None)


def refactoring_corp_name(corp_name):
    """
    выцепляет нормальное имя предприятия, отбрасывая локацию

    :param corp_name:
    :return:
    """

    if isinstance(corp_name, str):
        words = corp_name.split()

        for word in words:
            if '(' in word:
                pos = words.index(word)
                corp_name = ' '.join(words[:pos])

            return corp_name
    else:
        return 'Физ.лица'


def counter_docs(list_vet_doc):
    """
    считает количество типов вет документов для каждой организации (corp)

    :param list_vet_doc: list из словарей
    :return: pandas.DataFrame, кол-во документов
    """
    df = pd.DataFrame(list_vet_doc)
    df['name_corp'] = df['name_corp'].apply(refactoring_corp_name)
    df = df.drop_duplicates('vetDoc')

    all_doc_count = df['vetDoc'].count()

    # unique_corp = pd.unique(df['name_corp'])
    # unique_types_service = pd.unique(df['type_service'])
    #
    # # TODO походу я раньше любил упороться, короче переделать с group_by или pivot_table
    # res = []
    # for name in unique_corp:
    #     single_name_from_corp = df[df['name_corp'] == name]
    #
    #     list_with_quantity_u_types = []
    #
    #     for u_type in unique_types_service:
    #         selected_types = single_name_from_corp[single_name_from_corp['type_service'] == u_type]
    #         quantity_type = selected_types['type_service'].count()
    #
    #         list_with_quantity_u_types.append(quantity_type)
    #
    #     corp_dict = {'наименование': name,
    #                  'кол-во док-ов': single_name_from_corp['vetDoc'].count()}
    #
    #     for u_type, quantity in zip(unique_types_service, list_with_quantity_u_types):
    #         corp_dict[u_type] = quantity
    #
    #     res.append(corp_dict)

    # pandas way
    pivot = pd.pivot_table(df,
                           columns=['type_service'],
                           index=['name_corp'],
                           values=['vetDoc'],
                           aggfunc='count').fillna(0).reset_index()
    pivot['quantity'] = pivot['vetDoc'].sum(axis=1)

    # rename columns
    my_columns = [x for _, x in pivot.columns]
    my_columns[0] = 'Предприятие'
    my_columns[-1] = 'Кол-во'
    pivot.columns = my_columns

    # return pd.DataFrame(res), all_doc_count
    return pivot, all_doc_count


# if __name__ == '__main__':
#     tmp = pd.read_csv('temp.csv')
#     # print(tmp)
#
#     pivot = pd.pivot_table(tmp,
#                            columns=['type_service'],
#                            index=['name_corp'],
#                            values=['vetDoc'],
#                            aggfunc='count').fillna(0).reset_index()
#     pivot['quantity'] = pivot['vetDoc'].sum(axis=1)
#
#     # rename columns
#     my_columns = [x for _, x in pivot.columns]
#     my_columns[0] = 'Предприятие'
#     my_columns[-1] = 'Кол-во'
#     pivot.columns = my_columns
#
#     pivot.to_excel('res.xlsx', float_format='%i')

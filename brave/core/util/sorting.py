"""

Implementation of case insensitive object sorting.

"""


def sort_object_insensitive_alpha(dictionary, attr_name):

    entity_list = {}
    sorted_list = []

    # this is pretty bad
    for entity in dictionary:
        entity_list[getattr(entity, attr_name).lower()] = entity

    # but this is worse :(
    for attr_name in sorted(entity_list.iterkeys()):
        sorted_list.append(entity_list[attr_name])

    return sorted_list
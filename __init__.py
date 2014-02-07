#This file is part nereid_contact module for Tryton.
#The COPYRIGHT file at the top level of this repository contains
#the full copyright notices and license terms.

from trytond.pool import Pool
from .contact import *


def register():
    Pool.register(
        Contact,
        module='nereid_contact', type_='model')

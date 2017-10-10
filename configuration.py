# This file is part of trytond-cash_bank module.
# The COPYRIGHT file at the top level of this repository
# contains the full copyright notices and license terms.

from trytond.pyson import Eval, Get
from trytond.pool import Pool
from trytond.model import (
    ModelSingleton, ModelView, ModelSQL, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)

__all__ = ['Configuration', 'ConfigurationAccount']


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Cash / Bank Configuration'
    __name__ = 'cash_bank.configuration'

    account_transfer = fields.MultiValue(fields.Many2One('account.account',
        'Account Transfer',
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('context', {}).get('company', -1)),
        ]))

    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field == 'account_transfer':
            return pool.get('cash_bank.configuration.account')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationAccount(ModelSQL, CompanyValueMixin):
    "Cash / Bank configuration Account"
    __name__ = 'cash_bank.configuration.account'

    account_transfer = fields.Many2One('account.account',
        'Account Transfer',
        domain=[
            ('kind', '!=', 'view'),
            ('company', '=', Eval('context', {}).get('company', -1)),
        ])

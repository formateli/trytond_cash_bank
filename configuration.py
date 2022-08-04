# This file is part of Cash & Bank module.
# The COPYRIGHT file at the top level of this repository contains
# the full copyright notices and license terms.
from trytond.pyson import Eval, Id
from trytond.pool import Pool
from trytond.model import (
    ModelSingleton, ModelView, ModelSQL, fields)
from trytond.modules.company.model import (
    CompanyMultiValueMixin, CompanyValueMixin)


class Configuration(
        ModelSingleton, ModelSQL, ModelView, CompanyMultiValueMixin):
    'Cash / Bank Configuration'
    __name__ = 'cash_bank.configuration'
    account_transfer = fields.MultiValue(fields.Many2One('account.account',
        'Account Transfer',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ('type', '!=', None),
            ('closed', '!=', True),
            ]))
    convertion_seq = fields.MultiValue(fields.Many2One(
            'ir.sequence', "Cash and Bank Convertion Sequence",
            domain=[
                ('company', 'in',
                    [Eval('context', {}).get('company', -1), None]),
                ('sequence_type', '=',
                    Id('cash_bank', 'sequence_type_cash_bank_convertion')),
                ]))
    month_allow = fields.MultiValue(fields.Selection([
        (None, ''),
        ('1', 'January'),
        ('2', 'Febrary'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
        ], 'Month Allowed', sort=False))


    @classmethod
    def multivalue_model(cls, field):
        pool = Pool()
        if field in {'account_transfer',}:
            return pool.get('cash_bank.configuration.account')
        if field == 'convertion_seq':
            return pool.get('cash_bank.configuration.sequences')
        if field == 'month_allow':
            return pool.get('cash_bank.configuration.other')
        return super(Configuration, cls).multivalue_model(field)


class ConfigurationAccount(ModelSQL, CompanyValueMixin):
    "Cash / Bank configuration Account"
    __name__ = 'cash_bank.configuration.account'
    account_transfer = fields.Many2One('account.account',
        'Account Transfer',
        domain=[
            ('company', '=', Eval('context', {}).get('company', -1)),
            ('type', '!=', None),
            ('closed', '!=', True),
            ])


class ConfigurationSequences(ModelSQL, CompanyValueMixin):
    'Configuration Sequences'
    __name__ = 'cash_bank.configuration.sequences'
    convertion_seq = fields.Many2One(
        'ir.sequence', "Cash and Bank Convertion Sequence",
        domain=[
            ('company', 'in',
                [Eval('context', {}).get('company', -1), None]),
            ('sequence_type', '=',
                Id('cash_bank', 'sequence_type_cash_bank_convertion')),
            ])


class ConfigurationOther(ModelSQL, CompanyValueMixin):
    'Configuration Other'
    __name__ = 'cash_bank.configuration.other'
    month_allow = fields.Selection([
        (None, ''),
        ('1', 'January'),
        ('2', 'Febrary'),
        ('3', 'March'),
        ('4', 'April'),
        ('5', 'May'),
        ('6', 'June'),
        ('7', 'July'),
        ('8', 'August'),
        ('9', 'September'),
        ('10', 'October'),
        ('11', 'November'),
        ('12', 'December'),
        ], 'Month Allowed', sort=False)

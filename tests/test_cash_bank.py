# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.

import unittest
import trytond.tests.test_tryton
import datetime
from decimal import Decimal
from trytond.tests.test_tryton import ModuleTestCase, with_transaction
from trytond.modules.company.tests import create_company, set_company
from trytond.modules.account.tests import create_chart, get_fiscalyear
from trytond.pool import Pool
from trytond.exceptions import UserError

class CashBankTestCase(ModuleTestCase):
    'Test CashBank module'
    module = 'cash_bank'

    @with_transaction()
    def test_cash_bank(self):
        pool = Pool()
        Account = pool.get('account.account')
        Config = pool.get('cash_bank.configuration')
        CashBank = pool.get('cash_bank.cash_bank')
        Receipt = pool.get('cash_bank.receipt')
        ReceiptType = pool.get('cash_bank.receipt_type')
        ReceiptLine = pool.get('cash_bank.receipt.line')
        DocumentType = pool.get('cash_bank.document.type')
        Document = pool.get('cash_bank.document')
        Docs = pool.get('cash_bank.document-cash_bank.receipt')

        company = create_company()
        with set_company(company):
            create_chart(company)
            self._create_fiscalyear(company)

            account_transfer, = Account.search([
                    ('name', '=', 'Main Expense'),
                    ])
            account_cash, = Account.search([
                    ('name', '=', 'Main Cash'),
                    ])
            account_revenue, = Account.search([
                    ('name', '=', 'Main Revenue'),
                    ])
            account_expense, = Account.search([
                    ('name', '=', 'Main Expense'),
                    ])

            payment_method = self._get_payment_method(
                company, 'journal_cash', account_cash)
    
            config = Config(
                account_transfer=account_transfer)
            config.save()

            cheque_type = DocumentType(name='Cheque')
            cheque_type.save()

            sequence = self._get_sequence(
                'Cash/Bank Sequence',
                'cash_bank.receipt',
                company)

            cash = CashBank(
                name='Main Cashier',
                type='cash',
                payment_method=payment_method,
                receipt_types=self._get_receipt_types(
                    'Cashier', sequence)
            )
            cash.save()
            self.assertEqual(len(cash.receipt_types), 2)

            bank = CashBank(
                name='Main Bank',
                type='bank',
                payment_method=payment_method,
                receipt_types=self._get_receipt_types(
                    'Bank', sequence)
            )
            bank.save()
            self.assertEqual(len(bank.receipt_types), 2)

            date = datetime.date.today()

            # Receipt Cash IN
            receipt = self._get_receipt(
                company, cash, 'in', date)

            receipt.cash = Decimal('100.0')
            receipt.save()

            self.assertEqual(receipt.state, 'draft')
            self.assertEqual(receipt.diff, Decimal('-100.0'))

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_revenue
            )
            
            receipt.lines = [line,]
            receipt.save()

            self.assertEqual(len(receipt.lines), 1)
            self.assertEqual(receipt.diff, Decimal('0.0'))

            Receipt.confirm([receipt,])
            self.assertEqual(receipt.state, 'confirmed')

            Receipt.post([receipt,])
            self.assertEqual(receipt.state, 'posted')
            self.assertEqual(receipt.move.state, 'posted')
            self._check_line_move(
                receipt.move,
                payment_method.debit_account,
                receipt.total, Decimal('0.0'))

            # Receipt Cash OUT
            receipt = self._get_receipt(
                company, cash, 'out', date)

            receipt.cash = Decimal('100.0')
            receipt.save()

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_expense
            )

            receipt.lines = [line,]
            receipt.save()

            Receipt.confirm([receipt,])
            Receipt.post([receipt,])
            self._check_line_move(
                receipt.move,
                payment_method.credit_account,
                Decimal('0.0'), receipt.total)

            # 'out' receipts can not create documents
            receipt = self._get_receipt(
                company, cash, 'out', date)
            with self.assertRaises(UserError):
                receipt.cash = Decimal('10.0')
                receipt.save()
                docs = [
                    self._get_document(
                        cheque_type, Decimal('20.0'), date, 'a'),
                    self._get_document(
                        cheque_type, Decimal('30.0'), date, 'b'),
                    self._get_document(
                        cheque_type, Decimal('40.0'), date, 'c'),
                ]
                receipt.documents = docs
                receipt.save()
            Receipt.delete([receipt,])

            # Receipt IN with cash and documents

            receipt = self._get_receipt(
                company, cash, 'in', date)
            receipt.cash = Decimal('10.0')

            docs = [
                self._get_document(
                    cheque_type, Decimal('20.0'), date, 'abc'),
                self._get_document(
                    cheque_type, Decimal('30.0'), date, 'def'),
                self._get_document(
                    cheque_type, Decimal('40.0'), date, 'ghi'),
            ]
            receipt.documents = docs
            receipt.save()

            self.assertEqual(len(receipt.documents), 3)
            self.assertEqual(receipt.total_documents, Decimal('90.0'))
            self.assertEqual(receipt.total, Decimal('100.0'))
            self.assertEqual(receipt.diff, Decimal('-100.0'))

            self._verify_document('abc', receipt.id)
            self._verify_document('def', receipt.id)
            self._verify_document('ghi', receipt.id)

            line = ReceiptLine(
                receipt=receipt,
                amount=Decimal('100.0'),
                account=account_revenue
            )
            receipt.lines = [line,]
            receipt.save()

            Receipt.confirm([receipt,])

            Receipt.delete([receipt,])
            docs = Docs.search([])
            self.assertEqual(len(docs), 0)

    def _verify_document(self, reference, receipt_id):
        pool = Pool()
        Document = pool.get('cash_bank.document')
        Docs = pool.get('cash_bank.document-cash_bank.receipt')

        doc = Document.search([
            ('reference', '=', reference)
        ])[0]

        docs = Docs.search(
            [('document', '=', doc.id)], order=[('id', 'ASC')])

        self.assertEqual(doc.last_receipt.id, receipt_id)
        self.assertEqual(receipt_id, docs[-1].receipt.id)

    def _get_document(self, type_, amount, date, reference):
        Document = Pool().get('cash_bank.document')
        doc = Document(
            type=type_,
            amount=amount,
            date=date,
            reference=reference
        )
        return doc

    def _check_line_move(self, move, account_ref, debit, credit):
        for line in move.lines:
            if line.account == account_ref:
                self.assertEqual(line.debit, debit)
                self.assertEqual(line.credit, credit)
            else:
                self.assertEqual(line.debit, credit)
                self.assertEqual(line.credit, debit)                

    def _get_receipt(
            self, company, cash_bank, receipt_type, date):
        pool = Pool()
        Receipt = pool.get('cash_bank.receipt')
        ReceiptType = pool.get('cash_bank.receipt_type')
    
        type_ = ReceiptType.search([
            ('cash_bank', '=', cash_bank.id),
            ('type', '=', receipt_type)])[0]

        receipt = Receipt(
            company=company,
            cash_bank=cash_bank,
            type=type_,
            date=date,
        )

        return receipt

    def _get_sequence(self, name, code, company, is_strict=False):
        pool = Pool()
        if is_strict:
            Sequence = pool.get('ir.sequence.strict')
        else:
            Sequence = pool.get('ir.sequence')
        seq = Sequence(
            name=name,
            code=code,
            company=company,
            type='incremental'
        )
        seq.save()
        return seq

    def _get_receipt_types(self, name, sequence):
        pool = Pool()
        ReceiptType = pool.get('cash_bank.receipt_type')
        types = ['in', 'out']

        res = []
        for t in types:
            rt = ReceiptType(
                name=name + ' ' + t,
                type=t,
                sequence=sequence
            )
            res.append(rt)
        return res

    def _get_payment_method(self, company, fs_id, account):
        pool = Pool()
        ModelData = pool.get('ir.model.data')
        Journal = pool.get('account.journal')
        PaymentMethod = pool.get('account.invoice.payment.method')

        journal = Journal(ModelData.get_id(
            'account', fs_id))

        payment_method = PaymentMethod(
            name=journal.name,
            company=company,
            journal=journal,
            credit_account=account,
            debit_account=account
        )

        return payment_method

    def _create_fiscalyear(self, company):
        pool = Pool()
        FiscalYear = pool.get('account.fiscalyear')
        InvoiceSequence = pool.get(
            'account.fiscalyear.invoice_sequence')

        invoice_seq = self._get_sequence(
            'Invoice Sequence', 'account.invoice', company.id, True)

        seq = InvoiceSequence()
        seq.company = company
        seq.out_invoice_sequence = invoice_seq
        seq.out_credit_note_sequence = invoice_seq
        seq.in_invoice_sequence = invoice_seq
        seq.in_credit_note_sequence = invoice_seq
        
        fy = get_fiscalyear(company)
        fy.invoice_sequences = [seq,]
        fy.save()
        FiscalYear.create_period([fy,])


def suite():
    suite = trytond.tests.test_tryton.suite()
    suite.addTests(unittest.TestLoader().loadTestsFromTestCase(
        CashBankTestCase))
    return suite

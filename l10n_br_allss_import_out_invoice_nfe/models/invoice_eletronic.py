# -*- coding: utf-8 -*-

from odoo import models


class AllssInvoiceEletronic(models.Model):
    _inherit = 'invoice.eletronic'

    def _create_partner(self, tag_nfe, destinatary):
        partner_id = super(AllssInvoiceEletronic, self)._create_partner(tag_nfe, destinatary)
        partner_id.write({
            'customer': True,
            'property_account_receivable_id': self._allss_get_account_receivable(
                partner_id.name),
        })
        return partner_id
    

    def _allss_get_next_code(self):
        """
        Método resonsável por gerar o próximo código para a conta contábil baseado no dado do
        prefixo do grupo de conta fornecido por contexto
        """
        code_prefix = self.env.context.get('l10n_br_allss_group_id').code_prefix_start
        if not code_prefix.endswith('.'):
            code_prefix += '.'
        obj_account_account = self.env.get('account.account')
        account_id = obj_account_account.search(
            [('code', 'like', ('%s%%' % code_prefix))], order='code desc', limit=1)
        if not account_id:
            return code_prefix + '1'.zfill(6)
        next_code = int(account_id.code.split('.')[-1])
        next_code += 1
        return code_prefix + str(next_code).zfill(6)


    def _allss_get_account_receivable(self, partner_name):
        """
        Método responsável por criar/encontrar a conta contábil de acordo com o nome do parceiro e
        grupo contábil fornecido por contexto
        :param partner_name: nome do parceiro
        :type partner_name: str
        :return: nova instância do objeto 'account.account'
        :rtype: object
        """
        obj_account_account = self.env.get('account.account')
        code = self._allss_get_next_code()
        group_id = self.env.context.get('allss_group_id').id
        account_ids = obj_account_account.search(
            [('name', 'ilike', partner_name), ('group_id', '=', group_id)])
        partner_ids = self.env.get('res.partner').search(
            [('property_account_receivable_id', 'in', account_ids.ids)])
        account_id = obj_account_account
        if not partner_ids and account_ids:
            account_id = account_ids[0]
        elif partner_ids and account_ids:
            account_id = account_ids.filtered(
                lambda a: a.id not in partner_ids.mapped('property_account_receivable_id').ids)
            if account_id:
                account_id = account_id[0]
        if not account_id:
            account_id = obj_account_account.create({
                'name': partner_name,
                'code': code,
                'group_id': group_id,
                'account_type': "asset_receivable",
                'reconcile': True,
            })
        return account_id.id
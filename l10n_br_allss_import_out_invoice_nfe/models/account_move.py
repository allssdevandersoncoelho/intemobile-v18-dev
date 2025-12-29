# -*- coding: utf-8 -*-
# © 2025 ALLSS Soluções em Sistemas LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)

# import re
# import base64
# import pytz
import logging

_logger = logging.getLogger(__name__)

from odoo import fields, models             #, _, Command
# from dateutil import parser
# from datetime import datetime
from lxml import objectify
from odoo.exceptions import UserError       #, ValidationError

# from odoo import api
# from contextlib import contextmanager


def convert(obj, conversion=None):
    if conversion:
        return conversion(obj.text)
    if isinstance(obj, objectify.StringElement):
        return str(obj)
    if isinstance(obj, objectify.IntElement):
        return int(obj)
    if isinstance(obj, objectify.FloatElement):
        return float(obj)
    raise f"Tipo não implementado {type(obj)}"


def get(obj, path, conversion=None):
    paths = path.split(".")
    index = 0
    for item in paths:
        if not item:
            continue
        if hasattr(obj, item):
            obj = obj[item]
            index += 1
        else:
            return None
    if len(paths) == index:
        return convert(obj, conversion=conversion)
    return None


# def cnpj_cpf_format(cnpj_cpf):
#     if len(cnpj_cpf) == 14:
#         cnpj_cpf = (cnpj_cpf[0:2] + '.' + cnpj_cpf[2:5] +
#                     '.' + cnpj_cpf[5:8] +
#                     '/' + cnpj_cpf[8:12] +
#                     '-' + cnpj_cpf[12:14])
#     else:
#         cnpj_cpf = (cnpj_cpf[0:3] + '.' + cnpj_cpf[3:6] +
#                     '.' + cnpj_cpf[6:9] + '-' + cnpj_cpf[9:11])
#     return cnpj_cpf


class AllssAccountMoveNfeImport(models.Model):
    _inherit = 'account.move'
    
    def default_l10n_br_allss_picking_type_id(self):
        l10n_br_allss_picking_type_id = self.env['stock.picking.type'].sudo().with_company(self.company_id).search([
            ('code', '=', 'outgoing'),
            ('company_id', 'in', [self.company_id.id, False])
        ], limit=1)
        return l10n_br_allss_picking_type_id.id if l10n_br_allss_picking_type_id else None
    
    # def _compute_picking(self):
    #     for r in self:
    #         pickings = self.env['stock.picking'].sudo().search([('l10n_br_allss_account_move_id', '=', r.id)])
    #         if pickings:
    #             r.l10n_br_allss_picking_ids = [(6, 0, pickings.ids)]
    #             r.l10n_br_allss_picking_count = len(pickings)

    l10n_br_allss_picking_type_id = fields.Many2one('stock.picking.type', 
                                                    string='Tipo de Operação', 
                                                    default=default_l10n_br_allss_picking_type_id,
                                                    copy=False, 
                                                    store=True,
                                                    domain="[('company_id', '=', company_id)]")
    # l10n_br_allss_picking_ids = fields.Many2many('stock.picking', 
    #                                             #  compute='_compute_picking', 
    #                                              string='Picking', 
    #                                              copy=False, 
    #                                              store=True)
    # l10n_br_allss_picking_count = fields.Integer(string='Picking count', 
    #                                             #  compute='_compute_picking', 
    #                                              default=0, 
    #                                              store=True)


    def _l10n_br_get_pickings(self):
        ''' Override to include pickings linked via l10n_br_allss_account_move_id '''
        pickings = super()._l10n_br_get_pickings()

        extra_pickings = self.env["stock.picking"].search([
            ("l10n_br_allss_account_move_id", "=", self.id),
        ])

        return (pickings | extra_pickings).filtered(lambda p: p)



    # def import_nfe(self, auto, company_id, nfe, nfe_xml, dfe, 
    #                partner_automation=False,
    #                account_invoice_automation=False, 
    #                tax_automation=False,
    #                supplierinfo_automation=False, 
    #                fiscal_position_id=False,
    #                payment_term_id=False, 
    #                account_move_dict=None, 
    #                purchase_order_automation=False):

    #     _logger.warning(f"Contexto import_nfe:{self.env.context}")
    #     account_move_dict = account_move_dict or {}
    #     partner_vals = self._get_company_account_move(auto, nfe, partner_automation)
    #     if not partner_vals:
    #         return False
    #     _logger.warning(f">>>>> ALLSS > import_nfe > partner_vals: {partner_vals}")

    #     if self.existing_account_move(auto, nfe, partner_vals):
    #         # self.sudo().message_post(body='NF-e já importada!')
    #         if auto:
    #             _logger.warning(f'>>>>> ALLSS > NF-e Import > NF-e já importada!')
    #             return False
    #         else:
    #             raise UserError('NF-e já importada!')

    #     account_move_dict.update(self.get_compra(nfe))
    #     purchase_order = account_move_dict.get('l10n_br_allss_xpedcom')
    #     _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order ({type(purchase_order)}): {purchase_order}")
    #     purchase_order_dict = self._l10n_br_allss_get_purchase_order_vals(purchase_order)       
    #     _logger.warning(f">>>>> ALLSS > import_nfe > purchase_order_dict ({type(purchase_order_dict)}): {purchase_order_dict}")

    #     company_id = self.env['res.company'].sudo().browse(partner_vals['company_id'])
        
    #     _logger.warning(f">>>>> ALLSS > import_nfe > company_id ({type(company_id)}): {company_id}")
        
    #     if not fiscal_position_id:
    #         fiscal_position_id = (purchase_order_dict and purchase_order_dict.get('fiscal_position_id')) or company_id.l10n_br_allss_fiscal_position_id_automation or False
        
    #     account_move_dict.update(partner_vals)
    #     account_move_dict.pop('destinatary')
    #     account_move_dict.update({
    #         'l10n_br_allss_nf_xml': base64.encodebytes(nfe_xml),
    #         'l10n_br_allss_nf_number': nfe.NFe.infNFe.ide.nNF,
    #         # 'name': nfe.NFe.infNFe.ide.nNF,
    #         'l10n_latam_document_number': nfe.NFe.infNFe.ide.nNF,
    #     })
    #     account_move_dict.update(self.get_protNFe(nfe, company_id))
    #     account_move_dict.update(self.get_main(nfe))
    #     partner = self.get_partner_nfe(
    #         nfe, partner_vals['destinatary'], partner_automation, dfe)
    #     account_move_dict.update(
    #         self.get_ide(nfe, partner_vals['move_type'], fiscal_position_id))
    #     account_move_dict.update(partner)
    #     if purchase_order_dict:
    #         account_move_dict.update(purchase_order_dict)
    #     account_move_dict.update(self.get_items(
    #         nfe, company_id, partner['partner_id'] or account_move_dict['partner_id'],
    #         account_move_dict, dfe,
    #         supplierinfo_automation, tax_automation, 
    #         fiscal_position_id=account_move_dict['fiscal_position_id'] \
    #                                 if 'fiscal_position_id' in account_move_dict \
    #                                         and account_move_dict['fiscal_position_id'] \
    #                                 else fiscal_position_id,
    #         purchase_order_id=purchase_order_dict and purchase_order_dict.get('purchase_id')
    #         or account_move_dict.get('purchase_id'),
    #         purchase_order_automation=purchase_order_automation
    #     ))
    #     # if not purchase_order_dict and purchase_order_automation:
    #     #     account_move_dict.update(self._l10n_br_allss_create_purchase_order_vals(
    #     #         account_move_dict, dfe))
    #     purchase_id = purchase_order_dict.get('purchase_id') or account_move_dict.get('purchase_id')
    #     if purchase_id:
    #         brw_purchase_order = self.env.get('purchase.order').sudo().browse(purchase_id)
    #         brw_purchase_order.state == 'draft' and brw_purchase_order.button_confirm()
    #     account_move_dict.update(self.get_infAdic(nfe))

    #     _logger.warning(f">>>>> ALLSS > import_nfe > move_type: {partner_vals['move_type']}")

    #     # invoice_default = self.env['account.move'].with_context(
    #     #     default_move_type=partner_vals['move_type'], default_company_id=company_id.id
    #     # ).default_get(['journal_id'])

    #     # journal_id = self.env['account.move'].with_context(
    #     #     force_company=company_id.id, 
    #     #     type=('sale' 
    #     #             if partner_vals['move_type']=='out_invoice' 
    #     #             else 'purchase')
    #     #     )._get_default_journal()

    #     tipo = 'sale' if partner_vals['move_type'] == 'out_invoice' else 'purchase'
    #     journal_id = self.l10n_br_allss_get_journal_id(company_id, tipo)

    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id ({type(journal_id)}): {journal_id}")
    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.id ({type(journal_id.id)}): {journal_id.id}")
    #     _logger.warning(f">>>>> ALLSS > import_nfe > journal_id.name ({type(journal_id.name)}): {journal_id.name}")

    #     account_move_dict.update({'journal_id': journal_id.id})

    #     if 'l10n_br_allss_ms_code' not in account_move_dict and 'l10n_br_allss_ms_code' in journal_id._fields and journal_id.l10n_br_allss_ms_code:
    #         account_move_dict.update({'l10n_br_allss_ms_code': journal_id.l10n_br_allss_ms_code.sudo().id})

    #     transport_data = []
    #     transp_1 = self.get_transp(nfe)
    #     if transp_1:
    #         transport_data += transp_1
    #     mod_frete = '9'
    #     if hasattr(nfe.NFe.infNFe, 'transp'):
    #         mod_frete = get(nfe.NFe.infNFe.transp, 'modFrete', str)
        
    #     # ALLSS - Campo "l10n_br_allss_shipping_mode" substituido pelo "l10n_br_edi_freight_model" do módulo "l10n_br_edi"
    #     # account_move_dict.update({'l10n_br_allss_shipping_mode': mod_frete})
    #     # account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})
    #     if mod_frete == "0":
    #         mod_frete = "CIF"
    #     elif mod_frete == "1":
    #         mod_frete = "FOB"
    #     elif mod_frete == "2":
    #         mod_frete = "Thirdparty"
    #     elif mod_frete == "3":
    #         mod_frete = "SenderVehicle"
    #     elif mod_frete == "4":
    #         mod_frete = "ReceiverVehicle"
    #     elif mod_frete == "9":
    #         mod_frete = "FreeShipping"
    #     else:
    #         mod_frete = ""
    #     account_move_dict.update({'l10n_br_edi_freight_model': mod_frete})

    #     transp_1 = self.get_reboque(nfe)
    #     if transp_1:
    #         transport_data += transp_1
    #     account_move_dict.update({'l10n_br_allss_trailer_ids': transport_data})
    #     account_move_dict.update({'l10n_br_allss_volume_ids': [(0, 0, self.get_vol(nfe))]})

    #     # account_move_dict.update({'l10n_br_edi_payment_method': nfe.NFe.pag.detPag[0].tPag 
    #     #                                                 if hasattr(nfe.NFe, 'pag') and hasattr(nfe.NFe.pag, 'detPag') and len(nfe.NFe.pag.detPag) > 0 
    #     #                                                 else '99'}).zfill(2)

    #     _logger.warning(f">>>>> ALLSS > import_nfe 🟢 str(nfe.NFe.pag.detPag[0].tPag {str(nfe.NFe.infNFe.pag.detPag[0].tPag)}")
    #     account_move_dict.update({
    #         'l10n_br_edi_payment_method': str(
    #             nfe.NFe.infNFe.pag.detPag[0].tPag
    #             if hasattr(nfe.NFe.infNFe, 'pag')
    #             and hasattr(nfe.NFe.infNFe.pag, 'detPag')
    #             and len(nfe.NFe.infNFe.pag.detPag) > 0
    #             else '99'
    #         ).zfill(2)
    #     })

    #     account_move_dict.update(self.get_cobr_dup(nfe))
    #     account_move_dict.update(self.get_det_pag(nfe))
    #     account_move_dict.pop('destinatary', False)
    #     if account_move_dict.get('fiscal_position_id') \
    #             and not isinstance(account_move_dict.get('fiscal_position_id'), int):
    #         account_move_dict['fiscal_position_id'] = account_move_dict.get('fiscal_position_id').id

    #     _logger.warning(f">>>>> ALLSS > import_nfe > account_move_dict para o create de account.move ({type(account_move_dict)}): {account_move_dict}")
    #     account_move = self.sudo().create(account_move_dict)
    #     _logger.warning(f">>>>> ALLSS > import_nfe > account_move ({type(account_move)}): {account_move}")
    #     return account_move
    

    

    def action_post(self):
        self = self.sudo().with_company(self.company_id)
        if self.l10n_br_allss_nf_status == "imported" and self.move_type == 'out_invoice':
            move_lines = []
            for line in self.invoice_line_ids:
                move_lines_values = {
                    'name': line.product_id.name,
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.quantity,
                    'product_uom': line.product_uom_id.id,
                } 
                move_lines.append((0, 0, move_lines_values))
            
            location_dest_id = self.partner_id.property_stock_customer.id or \
                self.l10n_br_allss_picking_type_id.default_location_dest_id.id
            
            if not self.l10n_br_allss_picking_type_id:
                raise UserError('Atenção! O tipo de Operação não está definido!')
            else:
                picking = {               
                    'partner_id': self.partner_id.id,
                    'location_id': self.l10n_br_allss_picking_type_id.default_location_src_id.id,  
                    'location_dest_id': location_dest_id,
                    'picking_type_id': self.l10n_br_allss_picking_type_id.id,
                    'move_ids': move_lines,
                    'origin': self.name,
                    'l10n_br_allss_account_move_id': self.id,
                }
                stock_picking = self.env['stock.picking'].sudo().with_company(self.company_id).sudo().create(picking)                
                stock_picking.action_confirm()
                stock_picking.action_assign()

                for move in stock_picking.move_ids:
                    self.env['stock.move.line'].sudo().create({
                        'move_id': move.id,
                        'product_id': move.product_id.id,
                        'product_uom_id': move.product_uom.id,
                        'qty_done': move.product_uom_qty,
                        'location_id': stock_picking.location_id.id,
                        'location_dest_id': stock_picking.location_dest_id.id,
                        'picking_id': stock_picking.id,
                    })

                # for line in self.invoice_line_ids:
                #     analytic_account = line.analytic_distribution and list(line.analytic_distribution.keys())[0] or False
                #     for move_line in stock_picking.move_line_ids_without_package:
                #         if analytic_account:
                #             move_line._allss_analytic_account_id = int(analytic_account)

                
                stock_picking.button_validate()
                # self._compute_picking()

        return super().action_post()
    

    # def l10n_br_allss_action_view_picking(self):
    #     """ This function returns an action that display existing picking orders of given purchase order ids. When only one found, show the picking immediately.
    #     """
    #     action = self.env.ref('stock.action_picking_tree_all')
    #     result = action.read()[0]
    #     # override the context to get rid of the default filtering on operation type
    #     result['context'] = {}
    #     pick_ids = self.mapped('l10n_br_allss_picking_ids')
    #     # choose the view_mode accordingly
    #     if not pick_ids or len(pick_ids) > 1:
    #         result['domain'] = "[('id','in',%s)]" % (pick_ids.ids)
    #     elif len(pick_ids) == 1:
    #         res = self.env.ref('stock.view_picking_form', False)
    #         form_view = [(res and res.id or False, 'form')]
    #         if 'views' in result:
    #             result['views'] = form_view + [(state,view) for state,view in result['views'] if view != 'form']
    #         else:
    #             result['views'] = form_view
    #         result['res_id'] = pick_ids.id
    #     return result


    
    def _allss_get_next_code_out_invoice(self):
        """
        Método resonsável por gerar o próximo código para a conta contábil baseado no dado do
        prefixo do grupo de conta fornecido por contexto
        """
        _logger.warning(f"Contexto atual:{self.env.context}")

        code_prefix = self.env.context.get('l10n_br_allss_group_id').code_prefix_start
        _logger.warning(f">> NEXT_CODE > code_prefix: {code_prefix}")
        if not code_prefix.endswith('.'):
            code_prefix += '.'

        _logger.warning(f">> NEXT_CODE > code_prefix depois od if: {code_prefix}")

        obj_account_account = self.env.get('account.account')
        account_id = obj_account_account.search(
            [('code', 'ilike', (code_prefix+'%'))], order='code desc', limit=1)
        
        _logger.warning(f">> NEXT_CODE > account_id: {account_id}")
        if not account_id:
            _logger.warning(f">> NEXT_CODE > dentro do if not account: code_prefix + '1'.zfill(6): {code_prefix + '1'.zfill(6)}")
            return code_prefix + '1'.zfill(6)
        next_code = int(account_id.code.split('.')[-1])
        next_code += 1
        _logger.warning(f">> NEXT_CODE > next_code retornado: {code_prefix + str(next_code).zfill(6)}")
        return code_prefix + str(next_code).zfill(6)


    def _allss_get_account_receivable_out_invoice(self, partner_name):
        """
        Método responsável por criar/encontrar a conta contábil de acordo com o nome do parceiro e
        grupo contábil fornecido por contexto
        :param partner_name: nome do parceiro
        :type partner_name: str
        :return: nova instância do objeto 'account.account'
        :rtype: object
        """
        _logger.warning(f">> CHEGOU _allss_get_account_receivable ")
        _logger.warning(f"Contexto _allss_get_account_receivable:{self.env.context}")

        #
        # wizard_account = self.env.context.get('l10n_br_allss_account_account_id')
        # _logger.warning(f"WIZARD ACCOUNT ==== {wizard_account}")

        # if wizard_account:
        #     return wizard_account.id
        #

        obj_account_account = self.env.get('account.account')
        code = self._allss_get_next_code_out_invoice()
        group_id = self.env.context.get('l10n_br_allss_group_id')
        account_ids = obj_account_account.search(
            [('name', 'ilike', partner_name), ('code', 'ilike', group_id.code_prefix_start+'%')])
        
        _logger.warning(f">>>> account_ids encontrados: {account_ids}")

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
            account_id = obj_account_account.sudo().create({
                'name': partner_name,
                'code': code,
                'group_id': group_id.id,
                'account_type': "asset_receivable",
                'reconcile': True,
            })

        
        return account_id.id

    def _create_partner(self, tag_nfe, destinatary):
        res = super()._create_partner(tag_nfe, destinatary)

        _logger.warning(f">>> ALLSS > tag_nfe: {tag_nfe}")
        _logger.warning(f">>> ALLSS > CONTEXTO _create_partner: {self.env.context}")

        if self.env.context.get('allss_nfe_import_type') == 'out_invoice':
            res.sudo().write({
                'property_account_receivable_id': self._allss_get_account_receivable_out_invoice(res.name)})

        return res
    
    def l10n_br_allss_get_journal_id(self, company_id, type):
        res = super().l10n_br_allss_get_journal_id(company_id, type)

        wizard_journal = self.env.context.get('l10n_br_allss_journal_id')
        if wizard_journal:
            return wizard_journal
        
        return res
    


    def create_account_move_line(self, item, company_id, partner_id, supplier_automation,
                                 tax_automation, fiscal_position_id=None, account_move_dict=None):
        
        result = super().create_account_move_line(item, company_id, partner_id, supplier_automation,
                                 tax_automation, fiscal_position_id=fiscal_position_id, account_move_dict=account_move_dict)

        account_move_line, operation = result

        # _logger.warning(f'=============account_move_dict: {account_move_dict}')
        # _logger.warning(f'=============operation: {operation}')


        
        # Atualiza a posição fiscal e cfop para a de Vendas (out_invoice)
        fiscal_position_out_invoice = self.env.ref('l10n_br_allss_import_out_invoice_nfe.l10n_br_allss_xml_import_out_invoice_fiscal_position',
                                                   raise_if_not_found=False)
        cfop_out_invoice = self.env.ref('l10n_br_allss_account_tax.l10n_br_allss_fiscal_cfop_6106')        
        account_move_line.update({
            'l10n_br_allss_fiscal_position_id': fiscal_position_out_invoice.id if fiscal_position_out_invoice else fiscal_position_id,
            'l10n_br_allss_cfop_id': cfop_out_invoice.id if cfop_out_invoice else False,
        })

        # Busca produto pelo código do marketplace (l10n_br_allss_codigo_marketplace)
        codigo = get(item.prod, 'cProd', str)   
        if codigo:
            marketplace_products = self.env['product.product'].search([
                ('l10n_br_allss_codigo_marketplace', '=', codigo)
            ])

            if len(marketplace_products) > 1:
                raise UserError(
                    '[Código do Produto Marketplace] presente em mais de um Produto! '
                    'Os códigos devem ser únicos.'
                )

            if marketplace_products:
                _logger.warning(f'FOUND marketplace_products: {marketplace_products}')
                product = marketplace_products[0]

                _logger.warning(
                    f'ALLSS Marketplace PRIORITÁRIO  {product.display_name}'
                )

                account_move_line.update({
                    'product_id': product.id,
                    'product_uom_id': product.uom_id.id
                })


        # Adiciona conta analítica na linha da fatura, caso venha no contexto
        analytic = self.env.context.get('l10n_br_allss_account_analytic_id')
        if analytic:
            account_move_line['analytic_distribution'] = {
                str(analytic.id): 100.0
            }


        # Atualiza a operação da Fatura para 'Vendas'
        operation_from_import = self.env['l10n.br.allss.fiscal.operation'].search([('name', '=', 'Venda')], limit=1)
        operation = operation_from_import if operation_from_import else operation

        return [account_move_line, operation]
    


    

    def import_nfe(self, auto, company_id, nfe, nfe_xml, dfe, 
                   partner_automation=False,
                   account_invoice_automation=False, 
                   tax_automation=False,
                   supplierinfo_automation=False, 
                   fiscal_position_id=False,
                   payment_term_id=False, 
                   account_move_dict=None, 
                   purchase_order_automation=False):

        _logger.warning(f"+++Contexto import_nfe:  {self.env.context}")

        move = super(AllssAccountMoveNfeImport, self.with_context(nfe_flow='sale')).import_nfe(
            auto, company_id, nfe, nfe_xml, dfe,
            partner_automation,
            account_invoice_automation,
            tax_automation,
            supplierinfo_automation,
            fiscal_position_id,
            payment_term_id,
            account_move_dict,
            purchase_order_automation
        )

        # Atualiza a posição fiscal para a de Vendas (out_invoice) na fatura
        fiscal_position_out_invoice = self.env.ref('l10n_br_allss_import_out_invoice_nfe.l10n_br_allss_xml_import_out_invoice_fiscal_position',
                                                   raise_if_not_found=False)
        latam_document_type = self.env.ref('l10n_br.dt_55', raise_if_not_found=False)



        # Atualiza a condição de pagamento da Fatura
        invoice_payment_term_id = self.env['account.payment.term'].search([('name', 'ilike', '15 dias')], limit=1)
        move.update({
            'invoice_payment_term_id': invoice_payment_term_id.id,
            'fiscal_position_id': fiscal_position_out_invoice.id if fiscal_position_out_invoice else fiscal_position_id,
            'l10n_latam_document_type_id': latam_document_type.id if latam_document_type else False,

        })

        return move
    

    def l10n_br_allss_get_tax_nfe_import(self, tax_name, tax_aliquot, tax_value, tax_automation,
                                         **kwargs):

        if self.env.context.get('nfe_flow') != 'sale':
            return super().l10n_br_allss_get_tax_nfe_import(
                tax_name, tax_aliquot, tax_value, tax_automation, **kwargs
            )
        
        # ===== FLUXO DE VENDA PARA IMPOSTOS NA IMPORTAÇÃO =====
        obj_account_tax = self.env.get('account.tax')
        obj_allss_account_tax = self.env.get('l10n.br.allss.account.tax')
        obj_account_tax_group = self.env.get('account.tax.group')
        obj_cst = self.env.get('l10n.br.allss.cst')
        tax_registration_id = self.env.get('l10n.br.allss.tax.registration').sudo().search(
            [
                '|',
                ('l10n_br_allss_code', '=', tax_name.upper()),
                ('l10n_br_allss_code', '=', tax_name)
            ])
        if not tax_registration_id:
            return []
        args_allss_account_tax = [
            ('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
            ('l10n_br_allss_cst_id.l10n_br_allss_cst', '=', kwargs.get('cst'))
        ]
        reason_exemption_id = False
        if kwargs.get('motivo_desoneracao'):
            reason_exemption_id = self.env.get('l10n.br.allss.reason.exemption').search(
                [('l10n_br_allss_code', '=', kwargs.get('motivo_desoneracao'))], limit=1).id
            args_allss_account_tax.append(
                ('l10n_br_allss_reason_exemption_id', '=', reason_exemption_id))
        allss_account_tax_id = obj_allss_account_tax.search(args_allss_account_tax, limit=1)
        cst_id = False
        if tax_registration_id and tax_automation and kwargs.get('cst'):
            cst_id = obj_cst.search(
                [('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
                ('l10n_br_allss_cst', '=', kwargs.get('cst'))], limit=1)
            if not cst_id:
                cst_id = obj_cst.sudo().create({
                    'l10n_br_allss_tax_registration_id': tax_registration_id.id,
                        'l10n_br_allss_cst': kwargs.get('cst'),
                        'name': tax_name + ' ' + kwargs.get('cst')
                    })
        if not allss_account_tax_id and tax_automation:
            allss_account_tax_id = obj_allss_account_tax.sudo().create(
                {'name': tax_name, 
                 'l10n_br_allss_tax_registration_id': tax_registration_id.id,
                 'l10n_br_allss_cst_id': cst_id.id if cst_id else False,
                 'l10n_br_allss_reason_exemption_id': reason_exemption_id,
                 'l10n_br_allss_modBC_id': kwargs.get('origem') and self.env.get(
                     'l10n.br.allss.modbc').search(
                     [('l10n_br_allss_code', '=', kwargs.get('origem')),
                      ('l10n_br_allss_tax_registration_id', '=', tax_registration_id.id),
                      ], limit=1).id or False,
                 })
        if allss_account_tax_id and tax_automation and kwargs.get('cst') and not allss_account_tax_id.l10n_br_allss_cst_id:
            allss_account_tax_id.l10n_br_allss_cst_id = cst_id
        amount_type = 'percent'
        price_include = False
        if tax_name.upper() in ('DESCONTO', 'FRETE', 'SEGURO', 'OUTROS'):
            amount_type = 'fixed'
        if tax_name.upper() in ('ICMS', 'PIS', 'COFINS', 'ICMSSUBSTITUTO', 'ICMSSTRET'):
            amount_type = 'division'
            price_include = 'tax_included'
        if amount_type != 'fixed':
            tax_name += ' %s%% Importado NF-e' % tax_aliquot
        if len(kwargs.get('cst') or '') == 3:
            tax_name += ' SN'
        tax_ids = obj_account_tax.search([
            ('l10n_br_allss_account_tax_id', 'in', allss_account_tax_id.ids),
            ('amount_type', '=', amount_type),
            ('amount', '=', amount_type == 'fixed' and tax_value or tax_aliquot),
            ('type_tax_use', '=', 'sale'),
            ('company_id', '=', self.env.company.id)
        ], limit=1)
        if not tax_ids and tax_automation:
            tax_group_id = obj_account_tax_group.search([('name', '=', tax_name)], limit=1).id
            if not tax_group_id:
                tax_group_id = obj_account_tax_group.sudo().create({'name': tax_name}).id
            if obj_account_tax.search([('name', '=', tax_name)]):
                tax_name += '*'
            tax_ids = obj_account_tax.sudo().create({
                'name': tax_name,
                'l10n_br_allss_account_tax_id': allss_account_tax_id.ids[0],
                'amount_type': amount_type,
                'type_tax_use': 'sale',
                'amount_mva': kwargs.get('icms_st_aliquota_mva') or 0,
                'base_reduction': kwargs.get('icms_aliquota_reducao_base') or 0,
                # 'l10n_br_allss_tax_rate_compute': amount_type != 'fixed' and not tax_aliquot,
                'l10n_br_allss_tax_rate_compute': False,
                'amount': amount_type == 'fixed' and tax_value or tax_aliquot,
                'price_include_override': price_include,
                'description': tax_name,
                'tax_group_id': tax_group_id,
            })
        return tax_ids and (4, tax_ids.ids[0], False) or []

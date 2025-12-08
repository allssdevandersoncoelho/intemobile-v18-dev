# from odoo import models, api, fields, re
import base64
import logging
from odoo import fields, models
from dateutil import parser
from datetime import datetime
from lxml import objectify
from odoo.exceptions import UserError


_logger = logging.getLogger(__name__)

def convert(obj, conversion=None):
    if conversion:
        return conversion(obj.text)
    if isinstance(obj, objectify.StringElement):
        return str(obj)
    if isinstance(obj, objectify.IntElement):
        return int(obj)
    if isinstance(obj, objectify.FloatElement):
        return float(obj)
    raise u"Tipo não implementado %s" % str(type(obj))


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

class AllssCodigoMarketplace(models.Model):
    _name = "allss.codigo.marketplace"
    _description = "Códigos Produtos Marketplaces"

    name = fields.Char('Código Produto Marketplace')

class AllssProductTemplate(models.Model):
    _inherit = 'product.template'
    ### ALLSS - 01/03/2024 - Renata Carrillo - Início
    l10n_br_allss_codigo_marketplace = fields.Many2many('allss.codigo.marketplace', string="Código Produto Marketplace")

class InvoiceEletronic(models.Model):
    _inherit = 'invoice.eletronic'

# ALLSS - 08/03/2024 - Renata Carrillo e Caíque Anastacio - Função (create_invoice_eletronic_item) originada do módulo 'br_nfe_import' da localização brasileira versão 12 (diretório: https://gitlab.com/allss_odoo/odoo-brasil branch 12.0)
# Cliente solicitou mais um campo para verificação do cProd (l10n_br_allss_codigo_marketplace), com isso foi necessário retornar a função nesse módulo para poder adicionar mais um if (linhas: 81 a 85)
    def create_invoice_eletronic_item(self, item, company_id, partner_id, supplier, product_automation):
        # res = super().create_invoice_eletronic_item(item, company_id, partner_id, supplier, product_automation)
        # product = locals().get('product', None)
        # codigo = locals().get('codigo', 'teste')
        codigo = get(item.prod, 'cProd', str)

        seller_id = self.env['product.supplierinfo'].search([
            ('name', '=', partner_id),
            ('product_code', '=', codigo)])

        product = None
        if seller_id:
            product = seller_id.product_id or \
                seller_id.product_tmpl_id.product_variant_id

        if not product and item.prod.cEAN and \
           str(item.prod.cEAN) != 'SEM GTIN':
            product = self.env['product.product'].search(
                [('barcode', '=', item.prod.cEAN)], limit=1)

        uom_id = self.env['uom.uom'].search([
            ('name', '=', str(item.prod.uCom))], limit=1).id

        ### ALLSS - 08/03/2024 - Renata Carrillo - Início
        '''Adição de uma nova camada de pesquisa pelo produto, usando o campo l10n_br_allss_codigo_marketplace'''
        if not product:
            _logger.warning(f'<<<<<<<< SIMULAÇÃO ALLSS >>>>>>>>>> {codigo}')
            product = self.env['product.product'].search([
            # ('l10n_br_allss_codigo_marketplace', 'ilike', codigo)]) ### ALLSS - 29/05/2024 - Renata Carrillo - Comentando trecho com problema
            ('l10n_br_allss_codigo_marketplace', '=', codigo)]) ### ALLSS - 29/05/2024 - Renata Carrillo - Atualizando operador comparativo para resolver problema.
            # _logger.warning(f'<<<<<<<<<<<< PRODUCT >>>>>>>>>>>> {product}')
            if len(product) > 1:
                raise UserError('[Código do Produto Marketplace] presente em mais de um Produto! Os códigos devem ser únicos.')
        ### ALLSS - 08/03/2024 - Renata Carrillo - Fim
            
        ### ALLSS - 20/10/2022 - Nathan Oliveira - Início
        '''Adição de uma nova camada de pesquisa pelo produto, usando a referência interna'''
        if not product:
            product = self.env['product.product'].search([
                ('default_code', '=', codigo)])
            if len(product) > 1:
                raise UserError('[Referência Interna] presente em mais de um Produto! A referência deve ser única.')
        ### ALLSS - 20/10/2022 - Nathan Oliveira - Fim

        if not uom_id:
            uom_id = product and product.uom_id.id or False
        product_id = product and product.id or False

        if product and product.uom_id.name != str(item.prod.uCom):
            uom_id = product.uom_id.id or False

        if not product and product_automation:
            product = self._create_product(
                company_id, supplier, item.prod, uom_id=uom_id)

        quantidade = item.prod.qCom
        preco_unitario = item.prod.vUnCom
        valor_bruto = item.prod.vProd
        desconto = 0
        if hasattr(item.prod, 'vDesc'):
            desconto = item.prod.vDesc
        seguro = 0
        if hasattr(item.prod, 'vSeg'):
            seguro = item.prod.vSeg
        frete = 0
        if hasattr(item.prod, 'vFrete'):
            frete = item.prod.vFrete
        outras_despesas = 0
        if hasattr(item.prod, 'vOutro'):
            outras_despesas = item.prod.vOutro
        indicador_total = str(item.prod.indTot)
        tipo_produto = product and product.fiscal_type or 'product'
        cfop = item.prod.CFOP
        ncm = item.prod.NCM
        cest = get(item, 'item.prod.CEST')
        nItemPed = get(item, 'prod.nItemPed')

        invoice_eletronic_Item = {
            'product_id': product_id, 'uom_id': uom_id,
            'quantidade': quantidade, 'preco_unitario': preco_unitario,
            'valor_bruto': valor_bruto, 'desconto': desconto, 'seguro': seguro,
            'frete': frete, 'outras_despesas': outras_despesas,
            'valor_liquido': valor_bruto - desconto + frete + seguro + outras_despesas,
            'indicador_total': indicador_total, 'tipo_produto': tipo_produto,
            'cfop': cfop, 'ncm': ncm, 'product_ean': item.prod.cEAN,
            'product_cprod': codigo, 'product_xprod': item.prod.xProd,
            'cest': cest, 'item_pedido_compra': nItemPed,
        }
        if hasattr(item.imposto, 'ICMS'):
            invoice_eletronic_Item.update(self._get_icms(item.imposto))
        if hasattr(item.imposto, 'ISSQN'):
            invoice_eletronic_Item.update(self._get_issqn(item.imposto.ISSQN))

        if hasattr(item.imposto, 'IPI'):
            invoice_eletronic_Item.update(self._get_ipi(item.imposto.IPI))

        invoice_eletronic_Item.update(self._get_pis(item.imposto.PIS))
        invoice_eletronic_Item.update(self._get_cofins(item.imposto.COFINS))

        if hasattr(item.imposto, 'II'):
            invoice_eletronic_Item.update(self._get_ii(item.imposto.II))

        return self.env['invoice.eletronic.item'].create(
            invoice_eletronic_Item)

        # '''Adição de uma nova camada de pesquisa pelo produto, usando a Código Produto Marketplace'''
        # _logger.warning(f'<<<<<<<<<<<< ANTES DO IF >>>>>>>>>>>>')
        # if not product:
        #     _logger.warning(f'<<<<<<<< SIMULAÇÃO ALLSS >>>>>>>>>> {codigo}')
        #     product = self.env['product.product'].search([
        #         ('l10n_br_allss_codigo_marketplace', 'ilike', codigo)])
        #         # (codigo, 'ilike', 'l10n_br_allss_codigo_marketplace')])
        #     _logger.warning(f'<<<<<<<<<<<< PRODUCT >>>>>>>>>>>> {product}')

        # res = super().create_invoice_eletronic_item(item, company_id, partner_id, supplier, product_automation)
        # return res

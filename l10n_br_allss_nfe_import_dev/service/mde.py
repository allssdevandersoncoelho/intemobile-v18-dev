import re
import base64
import gzip
import io
import logging

_logger = logging.getLogger(__name__)

import os
import sys

from datetime import datetime

try:
    # from pytrustnfe.certificado import Certificado
    # from pytrustnfe.nfe import consulta_distribuicao_nfe
    # from pytrustnfe.nfe import recepcao_evento_manifesto
    # from pytrustnfe.nfe import download_nfe
    # Obtém o diretório atual deste módulo atual
    diretorio_atual = os.path.dirname(__file__)
    # Calcula o caminho relativo para a pasta pyboleto
    libs = os.path.abspath(os.path.join(diretorio_atual, '..', '..',  'l10n_br_allss_base', 'lib', 'PyTrustNFe'))
    sys.path.append(libs)
    import pytrustnfe
    from pytrustnfe.certificado import Certificado
    from pytrustnfe.nfe import consulta_distribuicao_nfe
    from pytrustnfe.nfe import recepcao_evento_manifesto
    from pytrustnfe.nfe import download_nfe
except ImportError:
    _logger.info('Cannot import pytrustnfe', exc_info=True)


def __certificado(company):
    cert = company.with_context({'bin_size': False}).l10n_br_allss_certificate
    cert_pfx = base64.decodebytes(cert)
    certificado = Certificado(cert_pfx, company.l10n_br_allss_cert_password)
    return certificado


def _format_nsu(nsu):
    return "%015d" % (int(nsu),)


def distribuicao_nfe(company, ultimo_nsu, **kwargs):
    ultimo_nsu = _format_nsu(ultimo_nsu)
    if company.l10n_br_allss_certificate:
        company_cert = company
    elif company.parent_id and company.parent_id.l10n_br_allss_certificate:
        company_cert = company.parent_id.l10n_br_allss_certificate
    
    _logger.warning(f">>>>>>>>>> ALLSS > distribuicao_nfe > kwargs ({type(kwargs)}): {kwargs}")
    
    certificado = __certificado(company_cert)
    cnpj_partner = re.sub('[^0-9]', '', company.vat)
    result = consulta_distribuicao_nfe(
        cnpj_cpf=cnpj_partner,
        ultimo_nsu=ultimo_nsu,
        estado=company.partner_id.state_id.l10n_br_allss_ibge_code,
        certificado=certificado,
        ambiente=kwargs.get('env_type'),
        modelo='55',
    )

    _logger.warning(f">>>>>>>>>> ALLSS > distribuicao_nfe > result ({type(result)}): {result}")

    retorno = result['object'].getchildren()[0]

    _logger.warning(f">>>>>>>>>> ALLSS > distribuicao_nfe > retorno ({type(retorno)}): {retorno}")

    if retorno.cStat == 138:
        nfe_list = []
        for doc in retorno.loteDistDFeInt.docZip:
            _logger.warning(f">>>>>>>>>> ALLSS > distribuicao_nfe > doc ({type(doc)}): {doc}")
            orig_file_desc = gzip.GzipFile(
                mode='r',
                fileobj=io.BytesIO(
                    base64.b64decode(str(doc)))
            )
            orig_file_cont = orig_file_desc.read()
            orig_file_desc.close()

            nfe_list.append({
                'xml': orig_file_cont, 'schema': doc.attrib['schema'],
                'NSU': doc.attrib['NSU']
            })

        return {
            'code': retorno.cStat,
            'message': retorno.xMotivo,
            'list_nfe': nfe_list,
            'file_returned': result['received_xml']
        }
    else:
        return {
            'code': retorno.cStat,
            'message': retorno.xMotivo,
            'file_sent': result['sent_xml'],
            'file_returned': result['received_xml']
        }


def send_event(company, nfe_key, method, lote, justificativa=None, **kwargs):
    certificado = __certificado(company)
    cnpj_partner = re.sub('[^0-9]', '', company.vat)
    result = {}

    ide = "ID%s%s%s" % (kwargs['evento']['tpEvento'], nfe_key, '01')
    manifesto = {
        'Id': ide,
        'cOrgao': 91,
        'tpAmb': kwargs.get('env_type'),
        'CNPJ': cnpj_partner,
        'chNFe': nfe_key,
        'dhEvento': datetime.now().strftime('%Y-%m-%dT%H:%M:%S-00:00'),
        'nSeqEvento': 1,
        'identificador': ide,
        'tpEvento': kwargs['evento']['tpEvento'],
        'descEvento': kwargs['evento']['descEvento'],
        'xJust': justificativa if justificativa else '',
    }
    result = recepcao_evento_manifesto(
        certificado=certificado,
        evento=method,
        eventos=[manifesto],
        ambiente=kwargs.get('env_type'),
        idLote=lote,
        estado='91',
        modelo='55',
    )

    retorno = result['object'].getchildren()[0]

    if retorno.cStat == 128:
        inf_evento = retorno.retEvento[0].infEvento
        return {
            'code': inf_evento.cStat,
            'message': inf_evento.xMotivo,
            'file_sent': result['sent_xml'],
            'file_returned': result['received_xml']
        }
    else:
        return {
            'code': retorno.cStat,
            'message': retorno.xMotivo,
            'file_sent': result['sent_xml'],
            'file_returned': result['received_xml']
        }


def exec_download_nfe(company, list_nfe, **kwargs):
    certificado = __certificado(company)
    cnpj_partner = re.sub('[^0-9]', '', company.vat)
    result = download_nfe(
        estado=company.partner_id.state_id.l10n_br_allss_ibge_code,
        certificado=certificado,
        ambiente=kwargs.get('env_type'),
        cnpj_cpf=cnpj_partner,
        chave_nfe=list_nfe[0],
        modelo='55')

    retorno = result['object'].getchildren()[0]

    if retorno.cStat == '139':
        nfe = retorno.retNFe[0]
        if nfe.cStat == '140':
            return {
                'code': nfe.cStat, 'message': nfe.xMotivo.valor,
                'file_sent': result.envio.xml,
                'file_returned': nfe.procNFe.valor.encode('utf-8'),
                'nfe': nfe
            }
        else:
            return {
                'code': nfe.cStat, 'message': nfe.xMotivo.valor,
                'file_sent': result.envio.xml,
                'file_returned': result.resposta.xml
            }

    else:
        return {
            'code': retorno.cStat,
            'message': retorno.xMotivo,
            'file_sent': result['sent_xml'],
            'file_returned': result['received_xml'],
            'object': retorno,
        }

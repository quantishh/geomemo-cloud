import os
import logging
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
from OpenSSL import SSL # Needed for methods

# Get a logger for this file
logger = logging.getLogger(__name__)

class CustomClientContextFactory(ScrapyClientContextFactory):

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        """
        Initializes the context factory from crawler settings.
        We get the cert_path from settings and store it on the instance.
        """
        instance = super().from_crawler(crawler, *args, **kwargs)
        instance.cert_path = crawler.settings.get('BRIGHTDATA_CERT_PATH')
        logger.info(f"CustomClientContextFactory initialized. Cert path: {instance.cert_path}")
        return instance

    def getContext(self, hostname=None, port=None):
        """
        Overrides the base getContext method to load our custom CA.
        This is the simplest and most robust way to add a trusted root.
        """
        # Get the default context from the parent class
        try:
            # Get the base context (this is the method that Scrapy calls)
            ctx = super().getContext(hostname, port)
        except Exception as e:
            logger.error(f"Error getting default SSL context from parent: {e}")
            # Fallback to creating a basic context if super() fails
            ctx = SSL.Context(self.method) # self.method is inherited

        # Get the custom CA path we stored in from_crawler
        cert_path = getattr(self, 'cert_path', None)

        # Check if the custom cert file exists at the correct path
        if cert_path and os.path.exists(cert_path):
            try:
                # This is the correct, modern way to add a trusted CA file
                ctx.load_verify_locations(cafile=cert_path)
                logger.info(f"Successfully loaded custom CA from {cert_path}")
            except SSL.Error as e:
                logger.error(f"OpenSSL Error loading custom CA {cert_path}: {e}")
            except Exception as e:
                logger.error(f"General Error loading custom CA {cert_path}: {e}")
        elif cert_path:
            logger.warning(f"Custom CA file not found: {cert_path}. Using default system CAs.")
        else:
             logger.debug("BRIGHTDATA_CERT_PATH not set. Using default system CAs.")
            
        return ctx

    # By REMOVING the 'creatorForNetloc' method, we let Scrapy's
    # base class handle it, and it will correctly call our
    # overridden getContext() method above. This avoids all the
    # TypeErrors and AttributeErrors we were seeing.
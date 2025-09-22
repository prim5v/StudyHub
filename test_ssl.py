import cloudinary
import cloudinary.uploader

cloudinary.config(
    cloud_name="dl9ismfbn",
    api_key="793953662339596",
    api_secret="nIsVkHOs6yMXAHaEVagmMRKS9UE",
    secure=True
)

result = cloudinary.uploader.upload("test.pdf", resource_type="raw")
print(result["secure_url"])

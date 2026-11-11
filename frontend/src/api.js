const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
export function getToken(){ return localStorage.getItem('finpay_token') }
export async function request(path, options={}) {
  const headers = {'Content-Type':'application/json', ...(options.headers||{})}
  const token = getToken()
  if(token) headers.Authorization = `Bearer ${token}`
  const response = await fetch(`${API}${path}`, {...options, headers})
  const data = await response.json().catch(()=>({detail:'Unexpected server response'}))
  if(!response.ok) throw new Error(data.detail || 'Request failed')
  return data
}
export async function login(email,password){
  const data = await request('/auth/login',{method:'POST',body:JSON.stringify({email,password})})
  localStorage.setItem('finpay_token',data.access_token)
  localStorage.setItem('finpay_user',JSON.stringify(data.user))
  return data.user
}
